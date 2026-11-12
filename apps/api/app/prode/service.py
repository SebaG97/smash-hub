"""Prode contests: candidates, predictions, locking and settling (ADR-020)."""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from app.links import service as links
from app.prode import engine
from app.prode.models import (
    ProdeAchievement,
    ProdeAuditEntry,
    ProdeCandidate,
    ProdeContest,
    ProdePrediction,
    ProdePredictionHistory,
    ProdeQuestion,
    ProdeScore,
)


class ProdeError(Exception):
    """A request the contest cannot take; the message is shown to the reader."""

    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def _now():
    return datetime.now(UTC)


def audit(s, contest, action, actor, **details):
    s.add(ProdeAuditEntry(contest_id=contest.id, action=action, actor=actor, details=details))


def sync_candidates(s, contest, entrants, seeds):
    """Mirror start.gg's entrants: newcomers are added, those who left are marked
    withdrawn (never deleted: someone may have picked them). Returns whether anything
    changed."""
    current = {
        c.startgg_player_id: c
        for c in s.scalars(select(ProdeCandidate).where(ProdeCandidate.contest_id == contest.id))
    }
    changed, now, present = False, _now(), set()
    for e in entrants:
        pid = str(e["startgg_player_id"])
        present.add(pid)
        values = dict(
            startgg_entrant_id=str(e.get("startgg_entrant_id") or "") or None,
            tag=(e.get("gamer_tag") or e.get("tag") or pid)[:120],
            prefix=(e.get("prefix") or None) and e["prefix"][:80],
            seed=seeds.get(pid),
        )
        row = current.get(pid)
        if row is None:
            s.add(ProdeCandidate(contest_id=contest.id, startgg_player_id=pid, **values))
            changed = True
            continue
        if row.withdrawn_at is not None:
            row.withdrawn_at, changed = None, True
        for key, value in values.items():
            if getattr(row, key) != value:
                setattr(row, key, value)
                changed = True
    for pid, row in current.items():
        if pid not in present and row.withdrawn_at is None:
            row.withdrawn_at, changed = now, True
    return changed


def create(s, *, slug, tournament, event, entrants, seeds, actor):
    if s.scalar(select(ProdeContest).where(ProdeContest.startgg_event_slug == event["slug"])):
        raise ProdeError("Este evento ya tiene Prode.")
    # A start confirmed by organizers (SH-FIX-01) wins over start.gg's event and tournament.
    if tournament.get("startAtConfirmed"):
        starts = tournament["startAt"]
    else:
        starts = event.get("startAt") or tournament.get("startAt")
    contest = ProdeContest(
        tournament_slug=slug,
        startgg_event_id=str(event["id"]),
        startgg_event_slug=event["slug"],
        name=tournament["name"][:200],
        event_name=(event.get("name") or "")[:200] or None,
        locks_at=datetime.fromtimestamp(starts, UTC) if starts else None,
        rules=dict(engine.DEFAULT_RULES),
        created_by=actor,
    )
    s.add(contest)
    s.flush()
    for kind in engine.KINDS:
        s.add(ProdeQuestion(contest_id=contest.id, kind=kind))
    sync_candidates(s, contest, entrants, seeds)
    audit(s, contest, "create", actor, locks_at=contest.locks_at and contest.locks_at.isoformat())
    return contest


def closed(contest, now):
    return contest.status != "open" or (contest.locks_at is not None and now >= contest.locks_at)


def set_locks_at(s, contest, when, actor, now):
    """Move an open contest's close (SH-FIX-01). Idempotent: the same time changes nothing.
    Picks and participants are untouched. A time already past is refused: closing now is
    what "Cerrar ahora" is for."""
    if closed(contest, now):  # locked, settled, void, or its close already passed
        raise ProdeError("Solo se puede cambiar el cierre de un Prode abierto.")
    if when <= now:
        raise ProdeError("El nuevo cierre tiene que ser posterior a este momento.", 422)
    if contest.locks_at is not None and contest.locks_at == when:
        return False
    audit(
        s,
        contest,
        "set_locks_at",
        actor,
        before=contest.locks_at and contest.locks_at.isoformat(),
        after=when.isoformat(),
    )
    contest.locks_at = when
    return True


def lock_if_due(s, contest):
    """Lock an open contest whose start time passed (nobody needs to press anything)."""
    if contest.status == "open" and contest.locks_at and _now() >= contest.locks_at:
        contest.status, contest.locked_at = "locked", _now()
        audit(s, contest, "auto_lock", "sistema")
        return True
    return False


def _questions(s, contest):
    return {
        q.kind: q
        for q in s.scalars(select(ProdeQuestion).where(ProdeQuestion.contest_id == contest.id))
    }


def save(s, contest_id, user, picks):
    """Store a forecaster's picks. The contest row is locked and the time is the
    database's, so nothing gets in after the close."""
    contest = s.get(ProdeContest, contest_id, with_for_update=True)
    if contest is None:
        raise ProdeError("No existe ese Prode.", 404)
    if closed(contest, s.scalar(select(func.now()))):
        raise ProdeError("El Prode ya cerró: no se pueden cambiar los pronósticos.")
    active = {
        c.startgg_player_id
        for c in s.scalars(
            select(ProdeCandidate).where(
                ProdeCandidate.contest_id == contest.id, ProdeCandidate.withdrawn_at.is_(None)
            )
        )
    }
    champion = picks.get("champion") or None
    runner_up = picks.get("runner_up") or None
    top8 = list(dict.fromkeys(picks.get("top8") or []))
    for pid in [champion, runner_up, *top8]:
        if pid and pid not in active:
            raise ProdeError("Elegiste a alguien que no está inscripto.", 422)
    if champion and champion == runner_up:
        raise ProdeError("El campeón y el subcampeón tienen que ser distintos.", 422)
    if len(top8) > 8:
        raise ProdeError("El Top 8 tiene 8 lugares.", 422)
    values = dict(champion=champion, runner_up=runner_up, top8=top8)
    questions = _questions(s, contest)
    current = {
        p.question_id: p
        for p in s.scalars(
            select(ProdePrediction).where(
                ProdePrediction.user_id == user.id,
                ProdePrediction.question_id.in_([q.id for q in questions.values()]),
            )
        )
    }
    for kind, value in values.items():
        question = questions[kind]
        row = current.get(question.id)
        if row is None:
            if not value:
                continue
            row = ProdePrediction(question_id=question.id, user_id=user.id, value=value)
            s.add(row)
        elif row.value == value:
            continue
        else:
            row.value = value
        s.flush()
        s.add(ProdePredictionHistory(prediction_id=row.id, value=value))
    return values


def picks_of(s, contest):
    """{user id: ({kind: value}, last saved)} for everyone who played the contest."""
    out = {}
    rows = s.execute(
        select(ProdePrediction, ProdeQuestion.kind)
        .join(ProdeQuestion, ProdeQuestion.id == ProdePrediction.question_id)
        .where(ProdeQuestion.contest_id == contest.id)
    ).all()
    for prediction, kind in rows:
        picks, saved = out.get(prediction.user_id, ({}, None))
        picks[kind] = prediction.value
        stamp = prediction.updated_at
        out[prediction.user_id] = (picks, max(saved, stamp) if saved and stamp else saved or stamp)
    return {user: data for user, data in out.items() if any(data[0].values())}


def _first_saved(s, contest):
    """{user id: first time they saved a pick in this contest} from the pick history."""
    return dict(
        s.execute(
            select(ProdePrediction.user_id, func.min(ProdePredictionHistory.created_at))
            .join(ProdePrediction, ProdePrediction.id == ProdePredictionHistory.prediction_id)
            .join(ProdeQuestion, ProdeQuestion.id == ProdePrediction.question_id)
            .where(ProdeQuestion.contest_id == contest.id)
            .group_by(ProdePrediction.user_id)
        ).all()
    )


def reconcile(s, existing, earned, *, contest_id, now, event_at=None):
    """Bring stored achievements in line with what is earned now, without deleting.

    existing: rows already stored for this scope; earned: {user id: [achievement]}. New
    ones are inserted; those still earned keep their row and created_at (the first
    recognition) and get the current wording; those no longer earned are revoked; revoked
    ones earned again are reactivated. Returns {"added", "kept", "revoked", "restored"}."""
    counts = dict(added=0, kept=0, revoked=0, restored=0)
    stored = {(row.user_id, row.kind): row for row in existing}
    wanted = {}
    for user_id, items in earned.items():
        for item in items:
            wanted.setdefault((user_id, item["kind"]), item)
    for key, item in wanted.items():
        row = stored.get(key)
        if row is None:
            s.add(
                ProdeAchievement(
                    user_id=key[0],
                    contest_id=contest_id,
                    event_at=event_at,
                    evidence=dict(detail=item["detail"]),
                    **item,
                )
            )
            counts["added"] += 1
            continue
        if row.status != "active":
            row.status, row.revoked_at = "active", None
            counts["restored"] += 1
        else:
            counts["kept"] += 1
        row.title, row.detail, row.rare = item["title"], item["detail"], item["rare"]
        row.evidence = dict(detail=item["detail"])
    for key, row in stored.items():
        if key not in wanted and row.status == "active":
            row.status, row.revoked_at = "revoked", now
            counts["revoked"] += 1
    return counts


def settle(s, contest, placements, *, actor, source):
    """Score everyone from start.gg's final placements. Scores are rebuilt; achievements
    are reconciled (SH-ACH-01): settling again after a correction keeps each one's first
    recognition, revokes what no longer holds and never duplicates."""
    if contest.status == "void":
        raise ProdeError("El Prode está anulado.")
    results = engine.results_from(placements)
    if not results["champion"] or len(results["top8"]) < 8:
        raise ProdeError("start.gg todavía no tiene el Top 8 final de este evento.")
    now = _now()
    for kind, question in _questions(s, contest).items():
        question.result, question.status = results[kind], "settled"
        question.result_source, question.settled_at = source, now
    played = picks_of(s, contest)
    rows = []
    for user_id, (picks, saved) in played.items():
        rows.append(
            dict(
                user_id=user_id,
                last_saved_at=saved,
                **engine.score(contest.rules or engine.DEFAULT_RULES, results, picks),
            )
        )
    ranked = engine.rank(rows)
    s.execute(delete(ProdeScore).where(ProdeScore.contest_id == contest.id))
    s.flush()
    for row in ranked:
        s.add(ProdeScore(contest_id=contest.id, **row))
    candidates = list(
        s.scalars(select(ProdeCandidate).where(ProdeCandidate.contest_id == contest.id))
    )
    earned = engine.achievements(
        contest.name,
        results,
        {user: picks for user, (picks, _) in played.items()},
        ranked,
        # The player behind each account comes from its link (ADR-021), if any.
        players=links.startgg_ids_for_users(s, list(played)),
        seeds={c.startgg_player_id: c.seed for c in candidates},
        tags={c.startgg_player_id: c.tag for c in candidates},
        placements={str(k): v for k, v in placements.items()},
        opened_at=contest.created_at,
        closes_at=contest.locked_at or contest.locks_at,
        first_saved=_first_saved(s, contest),
        last_saved={user: saved for user, (_, saved) in played.items()},
        candidates={c.startgg_player_id for c in candidates if c.withdrawn_at is None},
    )
    existing = list(
        s.scalars(select(ProdeAchievement).where(ProdeAchievement.contest_id == contest.id))
    )
    counts = reconcile(s, existing, earned, contest_id=contest.id, now=now, event_at=now)
    contest.status, contest.settled_at = "settled", now
    contest.locked_at = contest.locked_at or now
    s.flush()
    _lifetime(s, list(played))
    audit(s, contest, "settle", actor, source=source, players=len(ranked), achievements=counts)
    from app.achievements import runner

    runner.mark_dirty("prode")  # «La mufa no funciona» reads settled Prodes
    return ranked


def void_achievements(s, contest):
    """A voided contest stops counting: its achievements are revoked (not deleted) and
    the achievements across contests of its forecasters are recalculated."""
    now = _now()
    rows = list(
        s.scalars(select(ProdeAchievement).where(ProdeAchievement.contest_id == contest.id))
    )
    revoked = 0
    for row in rows:
        if row.status == "active":
            row.status, row.revoked_at = "revoked", now
            revoked += 1
    s.flush()
    users = list(s.scalars(select(ProdeScore.user_id).where(ProdeScore.contest_id == contest.id)))
    _lifetime(s, users)
    return revoked


def _lifetime(s, user_ids):
    """Reconcile the achievements across contests of these forecasters."""
    if not user_ids:
        return
    # Two settlements at once must not both insert the same achievement across contests.
    s.execute(select(func.pg_advisory_xact_lock(func.hashtextextended("prode:lifetime", 0))))
    settled = select(ProdeContest.id).where(ProdeContest.status == "settled")
    played = dict(
        s.execute(
            select(ProdeScore.user_id, func.count())
            .where(ProdeScore.user_id.in_(user_ids), ProdeScore.contest_id.in_(settled))
            .group_by(ProdeScore.user_id)
        ).all()
    )
    won = dict(
        s.execute(
            select(ProdeScore.user_id, func.count())
            .where(
                ProdeScore.user_id.in_(user_ids),
                ProdeScore.contest_id.in_(settled),
                ProdeScore.rank == 1,
                ProdeScore.points > 0,
            )
            .group_by(ProdeScore.user_id)
        ).all()
    )
    hits = set(
        s.execute(
            select(ProdeAchievement.user_id, ProdeAchievement.contest_id).where(
                ProdeAchievement.user_id.in_(user_ids),
                ProdeAchievement.kind == "oracle",
                ProdeAchievement.status == "active",
            )
        ).all()
    )
    history = {}
    for user_id, contest_id, rank, points in s.execute(
        select(ProdeScore.user_id, ProdeScore.contest_id, ProdeScore.rank, ProdeScore.points)
        .join(ProdeContest, ProdeContest.id == ProdeScore.contest_id)
        .where(ProdeScore.user_id.in_(user_ids), ProdeContest.status == "settled")
        .order_by(ProdeContest.settled_at, ProdeContest.created_at)
    ):
        history.setdefault(user_id, []).append((rank, points, (user_id, contest_id) in hits))
    existing = list(
        s.scalars(
            select(ProdeAchievement).where(
                ProdeAchievement.user_id.in_(user_ids), ProdeAchievement.contest_id.is_(None)
            )
        )
    )
    earned = engine.lifetime(played, won, history)
    reconcile(s, existing, earned, contest_id=None, now=_now())


def achievements_of(s, user_ids):
    rows = s.execute(
        select(ProdeAchievement, ProdeContest.name, ProdeContest.tournament_slug)
        .outerjoin(ProdeContest, ProdeContest.id == ProdeAchievement.contest_id)
        .where(
            ProdeAchievement.user_id.in_(user_ids),
            ProdeAchievement.status == "active",
            ProdeAchievement.hidden.is_(False),
        )
        .order_by(ProdeAchievement.rare.desc(), ProdeAchievement.created_at.desc())
    ).all()
    return [
        dict(
            kind=a.kind,
            title=a.title,
            detail=a.detail,
            rare=a.rare,
            contest=name,
            tournament_slug=slug,
            at=a.created_at.isoformat() if a.created_at else None,
        )
        for a, name, slug in rows
    ]
