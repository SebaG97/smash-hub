"""Achievement evaluation, storage and reading (SH-ACH-01).

The evaluator runs in the background (app.achievements.runner) or when an administrator
asks; never while serving a page. It reconciles: what is new is inserted with its first
recognition date, what still holds keeps that date, what no longer holds is revoked
(never deleted) and what holds again is reactivated.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.achievements import catalog, rules
from app.achievements.models import (
    AchievementAudit,
    AchievementRun,
    AchievementStat,
    AchievementSubject,
    PlayerAchievement,
    UserShowcase,
)
from app.auth.models import User
from app.competitions.models import (
    EntrantMember,
    Set,
    SetSelection,
    SetSide,
    TournamentParticipant,
)
from app.insights import engine as insights
from app.links.models import PlayerLink
from app.players.models import ExternalIdentity, Player
from app.prode.models import (
    ProdeAchievement,
    ProdeContest,
    ProdePrediction,
    ProdeQuestion,
    ProdeScore,
)

log = logging.getLogger(__name__)
LOCK_KEY = "achievements:evaluate"
MIN_UNIVERSE = 30  # below this the percentage is hidden ("muestra chica")
MIN_COVERAGE = 0.5  # partial data: hide the percentage below this coverage
MUFA_SHARE = 0.4
MUFA_MIN = 10


class AchievementError(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def now_utc():
    return datetime.now(UTC)


def audit(s, action, actor, *, achievement_id=None, player_id=None, **details):
    s.add(
        AchievementAudit(
            action=action,
            actor=actor,
            achievement_id=achievement_id,
            player_id=player_id,
            details=details,
        )
    )


# ---------------------------------------------------------------- context


def active_subjects(s):
    """{"spike"/"vbash": player id} of subjects registered, consented and active."""
    return {
        row.key: row.player_id
        for row in s.scalars(select(AchievementSubject))
        if row.active and row.consent_at is not None
    }


def load_context(s):
    data = insights.load(s)  # fresh, not the 5-minute cache of public pages
    eligible = {UUID(m.id) for m in data.matches}
    ctx = rules.Context(data=data, subjects=active_subjects(s))
    for set_id, round_number, best_of in s.execute(
        select(Set.id, Set.round_number, Set.best_of).where(Set.stats_eligible.is_(True))
    ):
        if set_id in eligible:
            ctx.sets[str(set_id)] = rules.SetInfo(round=round_number, best_of=best_of)
    for set_id, score, won in s.execute(
        select(SetSide.set_id, SetSide.score, SetSide.is_winner).where(
            SetSide.entrant_id.is_not(None)
        )
    ):
        info = ctx.sets.get(str(set_id))
        if info is None:
            continue
        if won:
            info.winner_score = score
        else:
            info.loser_score = score
    member = dict(
        s.execute(
            select(EntrantMember.entrant_id, TournamentParticipant.player_id).join(
                TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id
            )
        ).all()
    )
    from app.games.models import Character

    games = defaultdict(lambda: defaultdict(lambda: [{}, None]))
    for set_id, number, entrant_id, won, character in s.execute(
        select(
            SetSelection.set_id,
            SetSelection.game_number,
            SetSelection.entrant_id,
            SetSelection.won,
            Character.name,
        ).join(Character, Character.id == SetSelection.character_id)
    ):
        if set_id not in eligible:
            continue
        player = member.get(entrant_id)
        if player is None:
            continue
        game = games[str(set_id)][number]
        if character != "Random Character":
            game[0][player] = character
        if won:
            game[1] = player
    for set_id, numbers in games.items():
        ctx.games[set_id] = sorted(
            (n, chars, winner) for n, (chars, winner) in numbers.items() if winner is not None
        )
    for player_id, created in s.execute(
        select(PlayerLink.player_id, func.min(PlayerLink.created_at))
        .where(PlayerLink.unlinked_at.is_(None))
        .group_by(PlayerLink.player_id)
    ):
        ctx.links[player_id] = created
    ctx.mufa = _mufa(s)
    for player_id, aid in s.execute(
        select(PlayerAchievement.player_id, PlayerAchievement.achievement_id).where(
            PlayerAchievement.source == "manual", PlayerAchievement.status == "active"
        )
    ):
        ctx.manual.setdefault(player_id, set()).add(aid)
    return ctx


def hub_player_of(s, startgg_player_id):
    return s.scalar(
        select(ExternalIdentity.player_id).where(
            ExternalIdentity.external_id == f"player:{startgg_player_id}"
        )
    )


def _mufa(s):
    """«La mufa no funciona»: the most picked champion of a settled Prode (40 % or more
    of 10 or more forecasters) who won. Players resolved by start.gg id, never by tag."""
    out = []
    for contest in s.scalars(select(ProdeContest).where(ProdeContest.status == "settled")):
        question = s.scalar(
            select(ProdeQuestion).where(
                ProdeQuestion.contest_id == contest.id, ProdeQuestion.kind == "champion"
            )
        )
        if question is None or not question.result:
            continue
        votes = defaultdict(int)
        for value in s.scalars(
            select(ProdePrediction.value).where(ProdePrediction.question_id == question.id)
        ):
            if value:
                votes[str(value)] += 1
        total = sum(votes.values())
        if total < MUFA_MIN:
            continue
        favourite, n = max(votes.items(), key=lambda kv: kv[1])
        tied = sum(1 for v in votes.values() if v == n) > 1
        if tied or n / total < MUFA_SHARE or favourite not in {str(x) for x in question.result}:
            continue
        player = hub_player_of(s, favourite)
        if player is not None:
            out.append((player, contest.name, contest.settled_at, n / total))
    return out


# ---------------------------------------------------------------- evaluation


def _iso(value):
    return value.isoformat() if value else None


def _uuid(value):
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def reconcile(s, awards, now, *, backfill):
    """Apply the evaluation to player_achievements. Manual rows are never touched."""
    counts = dict(added=0, kept=0, revoked=0, restored=0)
    stored = {
        (row.player_id, row.achievement_id): row
        for row in s.scalars(
            select(PlayerAchievement).where(
                PlayerAchievement.source == "auto", PlayerAchievement.occurrence == ""
            )
        )
    }
    for key, award in awards.items():
        evidence = dict(award.evidence, detail=award.detail)
        evidence = {k: v for k, v in evidence.items() if v is not None}
        row = stored.get(key)
        if row is None:
            s.add(
                PlayerAchievement(
                    player_id=award.player,
                    achievement_id=award.achievement_id,
                    occurrence="",
                    event_at=award.event_at,
                    recognized_at=now,
                    backfilled=backfill,
                    tournament_id=_uuid(award.tournament_id),
                    event_id=_uuid(award.event_id),
                    set_id=_uuid(award.set_id),
                    opponent_player_id=_uuid(award.opponent),
                    evidence=evidence,
                    source="auto",
                    rule_version=rules.RULE_VERSION,
                    status="active",
                )
            )
            counts["added"] += 1
            continue
        if row.status != "active":
            row.status, row.revoked_at, row.revoked_reason = "active", None, None
            counts["restored"] += 1
        else:
            counts["kept"] += 1
        # The first recognition stays; the evidence follows today's data.
        row.event_at = award.event_at or row.event_at
        row.evidence = evidence
        row.tournament_id = _uuid(award.tournament_id)
        row.event_id = _uuid(award.event_id)
        row.set_id = _uuid(award.set_id)
        row.opponent_player_id = _uuid(award.opponent)
        row.rule_version = rules.RULE_VERSION
    for key, row in stored.items():
        if key not in awards and row.status == "active":
            row.status, row.revoked_at = "revoked", now
            row.revoked_reason = "Ya no se cumple con los datos actuales."
            counts["revoked"] += 1
    return counts


def _try_lock(s):
    return s.scalar(select(func.pg_try_advisory_xact_lock(func.hashtextextended(LOCK_KEY, 0))))


def run(engine, *, trigger, actor):
    """One full evaluation. Returns the run row's id and counts; a run already going on
    makes this one end as "skipped"."""
    started = now_utc()
    with Session(engine) as s, s.begin():
        row = AchievementRun(
            trigger=trigger[:20], actor=actor[:60], status="running", started_at=started
        )
        s.add(row)
        s.flush()
        run_id = row.id
    status, counts, error = "completed", {}, None
    try:
        with Session(engine) as s, s.begin():
            if not _try_lock(s):
                status = "skipped"
            else:
                previous = s.scalar(
                    select(func.count())
                    .select_from(AchievementRun)
                    .where(AchievementRun.status == "completed")
                )
                ctx = load_context(s)
                awards = rules.evaluate(ctx)
                counts = reconcile(s, awards, now_utc(), backfill=previous == 0)
                s.flush()
                counts["stats"] = refresh_stats(s, ctx)
                counts["players"] = len({p for p, _ in awards})
    except Exception as exc:  # recorded for the admin panel, then re-raised for logs
        status, error = "failed", type(exc).__name__
        log.exception("Achievement evaluation failed")
    with Session(engine) as s, s.begin():
        row = s.get(AchievementRun, run_id)
        row.status, row.finished_at, row.counts, row.error = status, now_utc(), counts, error
    return dict(id=str(run_id), status=status, counts=counts, error=error)


# ---------------------------------------------------------------- statistics


def _universes(s, ctx):
    data = ctx.data
    players = {p for m in data.matches for p in (m.winner, m.loser)}
    main16 = {f["player"] for f in data.finishes if rules._big(f)}
    main32 = {f["player"] for f in data.finishes if rules._big(f, 32)}
    with_characters = set(data.picks)
    out = dict(
        players=len(players),
        main16=len(main16),
        main32=len(main32),
        characters=len(with_characters),
        prode=s.scalar(
            select(func.count(func.distinct(ProdeScore.user_id))).where(
                ProdeScore.contest_id.in_(
                    select(ProdeContest.id).where(ProdeContest.status == "settled")
                )
            )
        )
        or 0,
    )
    for key, player in ctx.subjects.items():
        rivals = {
            m.loser if m.winner == player else m.winner
            for m in data.matches
            if player in (m.winner, m.loser)
        }
        out[f"vs_{key}"] = len(rivals)
    total_sets = len(data.matches) or 1
    coverage = dict(
        characters=len(ctx.games) / total_sets,
        city=(
            sum(1 for f in data.finishes if f.get("city")) / len(data.finishes)
            if data.finishes
            else 0
        ),
    )
    return out, coverage


def refresh_stats(s, ctx):
    """Holders, eligible universe, coverage and first holders of every achievement."""
    universes, coverage = _universes(s, ctx)
    now = now_utc()
    tags = ctx.data.tags
    player_rows = defaultdict(list)
    for player_id, aid, event_at, hidden in s.execute(
        select(
            PlayerAchievement.player_id,
            PlayerAchievement.achievement_id,
            PlayerAchievement.event_at,
            PlayerAchievement.hidden,
        ).where(PlayerAchievement.status == "active")
    ):
        player_rows[aid].append((player_id, event_at, hidden))
    prode_rows = defaultdict(list)
    for user_id, kind, created, hidden, name in s.execute(
        select(
            ProdeAchievement.user_id,
            ProdeAchievement.kind,
            ProdeAchievement.created_at,
            ProdeAchievement.hidden,
            User.display_name,
        )
        .join(User, User.id == ProdeAchievement.user_id)
        .where(ProdeAchievement.status == "active")
    ):
        prode_rows[kind].append((user_id, created, hidden, name))
    written = 0
    for entry in catalog.ACHIEVEMENTS:
        if entry.kind == "state":
            continue
        universe = universes.get(entry.universe)
        cov = None
        if entry.partial:
            cov = coverage["city"] if entry.id == "en_bici_hasta_cde" else coverage["characters"]
        first_at, first, verified = None, [], False
        if entry.scope == "player":
            rows = player_rows.get(entry.id, [])
            holders = len({p for p, _, _ in rows})
            dated = [(at, p) for p, at, hidden in rows if at is not None and not hidden]
            if dated:
                first_at = min(at for at, _ in dated)
                day = first_at.date()
                first = [dict(id=str(p), name=tags.get(p)) for at, p in dated if at.date() == day][
                    :5
                ]
                verified = not entry.partial
        else:
            rows = prode_rows.get(entry.id, [])
            holders = len({u for u, _, _, _ in rows})
            visible = [(at, u, name) for u, at, hidden, name in rows if not hidden]
            if visible:
                first_at = min(at for at, _, _ in visible)
                day = first_at.date()
                first = [dict(id=str(u), name=name) for at, u, name in visible if at.date() == day][
                    :5
                ]
                verified = True  # every Prode is recorded since the first one
        stat = s.get(AchievementStat, entry.id) or AchievementStat(achievement_id=entry.id)
        stat.holders, stat.universe, stat.coverage = holders, universe, cov
        stat.first_event_at, stat.first_holders, stat.first_verified = first_at, first, verified
        stat.computed_at = now
        s.add(stat)
        written += 1
    return written


def stat_view(entry, stat):
    """Holders and percentage, honest about small samples and partial data."""
    if entry.status == "pending":
        return dict(holders=0, universe=None, percent=None, label="Pendiente", note=None)
    if stat is None:
        return dict(holders=0, universe=None, percent=None, label="Sin calcular", note=None)
    holders, universe = stat.holders, stat.universe
    note = None
    percent = None
    if holders == 0:
        label = "Nadie todavía"
    elif entry.universe == "manual" or not universe:
        label = f"{holders} {'persona' if holders == 1 else 'personas'}"
    elif universe < MIN_UNIVERSE:
        label, note = "Muestra chica", f"Solo {universe} elegibles"
    elif stat.coverage is not None and stat.coverage < MIN_COVERAGE:
        label, note = "Datos parciales", "Cobertura insuficiente para un porcentaje"
    else:
        percent = round(100 * holders / universe, 1)
        label = _band(percent)
    return dict(
        holders=holders,
        universe=universe,
        percent=percent,
        label=label,
        note=note,
        coverage=round(stat.coverage, 3) if stat.coverage is not None else None,
        first=dict(
            at=_iso(stat.first_event_at),
            holders=stat.first_holders,
            verified=stat.first_verified,
        )
        if stat.first_event_at
        else None,
        computed_at=_iso(stat.computed_at),
    )


def _band(percent):
    if percent < 1:
        return "Rarísimo"
    if percent < 5:
        return "Escaso"
    if percent < 20:
        return "Poco frecuente"
    if percent <= 50:
        return "Frecuente"
    return "Muy frecuente"


# ---------------------------------------------------------------- reading


def stats_by_id(s):
    return {row.achievement_id: row for row in s.scalars(select(AchievementStat))}


def player_awards(s, player_id, *, include_hidden=False):
    query = select(PlayerAchievement).where(
        PlayerAchievement.player_id == player_id, PlayerAchievement.status == "active"
    )
    if not include_hidden:
        query = query.where(PlayerAchievement.hidden.is_(False))
    return list(s.scalars(query.order_by(PlayerAchievement.recognized_at)))


def prode_awards(s, user_id, *, include_hidden=False):
    query = (
        select(ProdeAchievement, ProdeContest.name, ProdeContest.tournament_slug)
        .outerjoin(ProdeContest, ProdeContest.id == ProdeAchievement.contest_id)
        .where(ProdeAchievement.user_id == user_id, ProdeAchievement.status == "active")
    )
    if not include_hidden:
        query = query.where(ProdeAchievement.hidden.is_(False))
    return list(s.execute(query.order_by(ProdeAchievement.created_at)).all())


def award_view(row, tags=None):
    entry = catalog.get(row.achievement_id)
    evidence = row.evidence or {}
    return dict(
        id=str(row.id),
        achievement_id=row.achievement_id,
        source="player",
        name=entry.name if entry else row.achievement_id,
        rarity=entry.rarity if entry else "comun",
        category=entry.category if entry else None,
        detail=evidence.get("detail"),
        evidence={k: v for k, v in evidence.items() if k != "detail"},
        event_at=_iso(row.event_at),
        recognized_at=_iso(row.recognized_at),
        backfilled=row.backfilled,
        manual=row.source == "manual",
        reason=row.reason,
        hidden=row.hidden,
        tournament_id=str(row.tournament_id) if row.tournament_id else None,
        opponent=dict(id=str(row.opponent_player_id), tag=(tags or {}).get(row.opponent_player_id))
        if row.opponent_player_id
        else None,
    )


def prode_award_view(row, contest, slug):
    entry = catalog.get(row.kind)
    return dict(
        id=str(row.id),
        achievement_id=row.kind,
        source="prode",
        name=entry.name if entry else row.title,
        rarity=entry.rarity if entry else ("raro" if row.rare else "comun"),
        category="prode",
        detail=row.detail,
        evidence={},
        event_at=_iso(row.event_at or row.created_at),
        recognized_at=_iso(row.created_at),
        backfilled=False,
        manual=False,
        reason=None,
        hidden=row.hidden,
        contest=contest,
        tournament_slug=slug,
    )


def linked_player(s, user_id):
    return s.scalar(
        select(PlayerLink.player_id).where(
            PlayerLink.user_id == user_id, PlayerLink.unlinked_at.is_(None)
        )
    )


def linked_user(s, player_id):
    return s.scalar(
        select(PlayerLink.user_id).where(
            PlayerLink.player_id == player_id, PlayerLink.unlinked_at.is_(None)
        )
    )


def tags_of(s, ids):
    ids = [i for i in ids if i]
    if not ids:
        return {}
    return dict(s.execute(select(Player.id, Player.tag).where(Player.id.in_(ids))).all())


def collection_progress(owned_ids, active_gates):
    """Per category and per collection: how many of the available achievements are owned
    (permanent ones only; states and limited editions do not count)."""
    out = {}
    for key, name in catalog.CATEGORIES.items():
        pool = [
            a
            for a in catalog.ACHIEVEMENTS
            if a.category == key and a.kind == "permanent" and _available(a, active_gates)
        ]
        out[key] = dict(name=name, owned=sum(1 for a in pool if a.id in owned_ids), total=len(pool))
    collections = {}
    for key, name in catalog.COLLECTIONS.items():
        pool = [
            a for a in catalog.ACHIEVEMENTS if a.collection == key and _available(a, active_gates)
        ]
        collections[key] = dict(
            name=name,
            owned=sum(1 for a in pool if a.id in owned_ids),
            total=len(pool),
            active=catalog.GATED.get(key) is None or catalog.GATED[key] in active_gates,
        )
    return out, collections


def _available(entry, active_gates):
    if entry.status == "pending":
        return False
    gate = catalog.GATED.get(entry.collection) if entry.collection else None
    return gate is None or gate in active_gates


def showcase_of(s, user_id):
    return [
        dict(slot=row.slot, achievement_id=row.achievement_id, source=row.source)
        for row in s.scalars(
            select(UserShowcase).where(UserShowcase.user_id == user_id).order_by(UserShowcase.slot)
        )
    ]


def set_showcase(s, user, items):
    """The owner's choice: up to three achievements they hold (player or Prode)."""
    if len(items) > 3:
        raise AchievementError("La vitrina tiene 3 lugares.", 422)
    keys = [(i["source"], i["achievement_id"]) for i in items]
    if len(set(keys)) != len(keys):
        raise AchievementError("No repitas un logro en la vitrina.", 422)
    player = linked_player(s, user.id)
    owned_player = (
        {r.achievement_id for r in player_awards(s, player, include_hidden=True)}
        if player
        else set()
    )
    owned_prode = {r.kind for r, _, _ in prode_awards(s, user.id, include_hidden=True)}
    for source, aid in keys:
        mine = owned_player if source == "player" else owned_prode
        if aid not in mine:
            raise AchievementError("Solo podés destacar logros que tenés.", 422)
    s.execute(text("DELETE FROM user_showcase WHERE user_id = :u"), {"u": user.id})
    s.flush()
    for slot, (source, aid) in enumerate(keys, start=1):
        s.add(UserShowcase(user_id=user.id, slot=slot, achievement_id=aid, source=source))
    return showcase_of(s, user.id)


def set_hidden(s, user, source, achievement_id, hidden):
    """The owner hides or shows one of their achievements on public pages."""
    if source == "player":
        player = linked_player(s, user.id)
        if player is None:
            raise AchievementError("Tu cuenta no está vinculada a un jugador.", 422)
        rows = list(
            s.scalars(
                select(PlayerAchievement).where(
                    PlayerAchievement.player_id == player,
                    PlayerAchievement.achievement_id == achievement_id,
                )
            )
        )
    else:
        rows = list(
            s.scalars(
                select(ProdeAchievement).where(
                    ProdeAchievement.user_id == user.id, ProdeAchievement.kind == achievement_id
                )
            )
        )
    if not rows:
        raise AchievementError("No tenés ese logro.", 404)
    for row in rows:
        row.hidden = hidden
    return len(rows)


# ---------------------------------------------------------------- administration


def set_subject(s, key, startgg_player_id, *, consent, active, actor):
    """Register who a collection is about, by start.gg player id (never by tag)."""
    if key not in catalog.GATED.values():
        raise AchievementError("No existe esa colección.", 404)
    player = hub_player_of(s, startgg_player_id)
    if player is None:
        raise AchievementError(
            "No hay un jugador del hub con ese ID de start.gg. Importá un torneo suyo primero.",
            422,
        )
    if active and not consent:
        raise AchievementError("Para activar la colección hace falta su consentimiento.", 422)
    row = s.get(AchievementSubject, key)
    before = None
    if row is None:
        row = AchievementSubject(key=key, player_id=player, startgg_player_id=startgg_player_id)
        s.add(row)
    else:
        before = dict(
            player_id=str(row.player_id),
            startgg_player_id=row.startgg_player_id,
            consent=row.consent_at is not None,
            active=row.active,
        )
    row.player_id, row.startgg_player_id = player, startgg_player_id
    if consent and row.consent_at is None:
        row.consent_at = now_utc()
    if not consent:
        row.consent_at = None
    row.active = active
    row.set_by = actor[:60]
    row.updated_at = now_utc()
    audit(
        s,
        "subject",
        actor,
        player_id=player,
        key=key,
        startgg_player_id=startgg_player_id,
        consent=consent,
        active=active,
        before=before,
    )
    return row


def subjects_view(s):
    rows = list(s.scalars(select(AchievementSubject)))
    tags = tags_of(s, [r.player_id for r in rows])
    return [
        dict(
            key=r.key,
            player_id=str(r.player_id),
            tag=tags.get(r.player_id),
            startgg_player_id=r.startgg_player_id,
            consent_at=_iso(r.consent_at),
            active=r.active,
            set_by=r.set_by,
            updated_at=_iso(r.updated_at),
        )
        for r in rows
    ]


def grant(s, player_id, achievement_id, reason, actor):
    entry = catalog.get(achievement_id)
    if entry is None or entry.status != "manual":
        raise AchievementError("Ese logro no se otorga a mano.", 422)
    gate = catalog.GATED.get(entry.collection) if entry.collection else None
    if gate and gate not in active_subjects(s):
        raise AchievementError("Esa colección no está activa.", 409)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AchievementError("Escribí el motivo (es público).", 422)
    if s.get(Player, player_id) is None:
        raise AchievementError("No existe ese jugador.", 404)
    row = s.scalar(
        select(PlayerAchievement).where(
            PlayerAchievement.player_id == player_id,
            PlayerAchievement.achievement_id == achievement_id,
            PlayerAchievement.occurrence == "",
        )
    )
    now = now_utc()
    if row is not None and row.status == "active":
        raise AchievementError("Ese jugador ya tiene ese logro.", 409)
    if row is None:
        row = PlayerAchievement(
            player_id=player_id,
            achievement_id=achievement_id,
            occurrence="",
            recognized_at=now,
            event_at=now,
            evidence={},
            source="manual",
            rule_version=rules.RULE_VERSION,
        )
        s.add(row)
    row.status, row.revoked_at, row.revoked_reason = "active", None, None
    row.granted_by, row.reason = actor[:60], reason[:500]
    s.flush()
    audit(s, "grant", actor, achievement_id=achievement_id, player_id=player_id, reason=reason)
    return row


def revoke(s, award_id, reason, actor):
    row = s.get(PlayerAchievement, award_id)
    if row is None or row.source != "manual":
        raise AchievementError("Solo se revocan a mano los logros manuales.", 404)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AchievementError("Escribí el motivo.", 422)
    if row.status != "active":
        raise AchievementError("Ese logro ya está revocado.", 409)
    row.status, row.revoked_at, row.revoked_reason = "revoked", now_utc(), reason[:200]
    audit(
        s,
        "revoke",
        actor,
        achievement_id=row.achievement_id,
        player_id=row.player_id,
        reason=reason,
    )
    return row


def manual_grants(s, limit=50):
    rows = list(
        s.scalars(
            select(PlayerAchievement)
            .where(PlayerAchievement.source == "manual")
            .order_by(PlayerAchievement.updated_at.desc())
            .limit(limit)
        )
    )
    tags = tags_of(s, [r.player_id for r in rows])
    return [
        dict(
            id=str(r.id),
            player_id=str(r.player_id),
            tag=tags.get(r.player_id),
            achievement_id=r.achievement_id,
            name=catalog.get(r.achievement_id).name if catalog.get(r.achievement_id) else None,
            status=r.status,
            reason=r.reason,
            granted_by=r.granted_by,
            recognized_at=_iso(r.recognized_at),
            revoked_reason=r.revoked_reason,
        )
        for r in rows
    ]


def status(s, settings):
    runs = list(
        s.scalars(select(AchievementRun).order_by(AchievementRun.started_at.desc()).limit(10))
    )
    stored = dict(
        s.execute(
            select(PlayerAchievement.status, func.count()).group_by(PlayerAchievement.status)
        ).all()
    )
    prode = dict(
        s.execute(
            select(ProdeAchievement.status, func.count()).group_by(ProdeAchievement.status)
        ).all()
    )
    return dict(
        auto=settings.achievements_auto,
        interval_seconds=settings.achievements_interval_seconds,
        catalog=dict(
            total=len(catalog.ACHIEVEMENTS),
            active=sum(1 for a in catalog.ACHIEVEMENTS if a.status == "active"),
            manual=sum(1 for a in catalog.ACHIEVEMENTS if a.status == "manual"),
            pending=sum(1 for a in catalog.ACHIEVEMENTS if a.status == "pending"),
        ),
        player_achievements=stored,
        prode_achievements=prode,
        subjects=subjects_view(s),
        runs=[
            dict(
                id=str(r.id),
                trigger=r.trigger,
                actor=r.actor,
                status=r.status,
                started_at=_iso(r.started_at),
                finished_at=_iso(r.finished_at),
                counts=r.counts,
                error=r.error,
            )
            for r in runs
        ],
    )


def recent_holders(s, entry, limit=12):
    """Latest public holders of one achievement (hidden ones are left out)."""
    if entry.scope == "player":
        rows = list(
            s.scalars(
                select(PlayerAchievement)
                .where(
                    PlayerAchievement.achievement_id == entry.id,
                    PlayerAchievement.status == "active",
                    PlayerAchievement.hidden.is_(False),
                )
                .order_by(PlayerAchievement.recognized_at.desc(), PlayerAchievement.event_at.desc())
                .limit(limit)
            )
        )
        tags = tags_of(s, [r.player_id for r in rows] + [r.opponent_player_id for r in rows])
        return [
            dict(
                player_id=str(r.player_id),
                name=tags.get(r.player_id),
                detail=(r.evidence or {}).get("detail"),
                event_at=_iso(r.event_at),
                recognized_at=_iso(r.recognized_at),
            )
            for r in rows
        ]
    rows = s.execute(
        select(ProdeAchievement, User.display_name, ProdeContest.name)
        .join(User, User.id == ProdeAchievement.user_id)
        .outerjoin(ProdeContest, ProdeContest.id == ProdeAchievement.contest_id)
        .where(
            ProdeAchievement.kind == entry.id,
            ProdeAchievement.status == "active",
            ProdeAchievement.hidden.is_(False),
            User.disabled_at.is_(None),
        )
        .order_by(ProdeAchievement.created_at.desc())
        .limit(limit)
    ).all()
    return [
        dict(
            user_id=str(r.user_id),
            name=name,
            detail=r.detail,
            contest=contest,
            event_at=_iso(r.event_at or r.created_at),
            recognized_at=_iso(r.created_at),
        )
        for r, name, contest in rows
    ]


def my_awards(s, user_id, entry):
    """The reader's own awards of one achievement, with their context."""
    if entry.scope == "player":
        player = linked_player(s, user_id)
        if player is None:
            return []
        rows = [
            r for r in player_awards(s, player, include_hidden=True) if r.achievement_id == entry.id
        ]
        tags = tags_of(s, [r.opponent_player_id for r in rows])
        return [award_view(r, tags) for r in rows]
    return [
        prode_award_view(r, c, slug)
        for r, c, slug in prode_awards(s, user_id, include_hidden=True)
        if r.kind == entry.id
    ]
