"""start.gg prefixes and the scene's teams (Mission 22).

A prefix ("BG", "GO"…) is typed at each registration, so it belongs to a participation,
not to a player: a player's prefix is the latest one they used in their last few
tournaments. Only prefixes an organizer approved are shown (see TeamPrefix).
"""

from collections import defaultdict
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.competitions.models import Tournament, TournamentParticipant
from app.teams.models import TeamPrefix

RECENT = 3  # a prefix used in any of the player's last three tournaments still counts
STATUSES = ("team", "alias", "shown", "hidden")


def clean_prefix(value):
    """start.gg prefix as shown: single spaces, no bars or brackets around it; None if empty."""
    text = " ".join((value or "").split()).strip("|[]() ")
    return text[:80] or None


def prefix_key(value):
    text = clean_prefix(value)
    return text.casefold() if text else None


def latest_prefixes(session, player_ids=None):
    """{player id: raw prefix} from each player's last RECENT published tournaments."""
    ranked = (
        select(
            TournamentParticipant.player_id,
            TournamentParticipant.prefix,
            func.row_number()
            .over(
                partition_by=TournamentParticipant.player_id,
                order_by=Tournament.starts_at.desc().nullslast(),
            )
            .label("n"),
        )
        .join(Tournament, Tournament.id == TournamentParticipant.tournament_id)
        .where(Tournament.published.is_(True))
    )
    if player_ids is not None:
        ranked = ranked.where(TournamentParticipant.player_id.in_(list(player_ids)))
    rows = ranked.subquery()
    found = {}
    for player, prefix, _ in session.execute(
        select(rows.c.player_id, rows.c.prefix, rows.c.n)
        .where(rows.c.n <= RECENT, rows.c.prefix.is_not(None))
        .order_by(rows.c.n)
    ):
        found.setdefault(player, prefix)
    return found


def rules(session):
    return {r.key: r for r in session.scalars(select(TeamPrefix))}


def resolve(rule_map, raw):
    """(label, team key) for an approved prefix, or None when it must not be shown."""
    rule = rule_map.get(prefix_key(raw))
    if rule is None or rule.status == "hidden":
        return None
    if rule.status == "alias":
        team = rule_map.get(rule.team)
        if team is None or team.status != "team":
            return None
        return team.name, team.key
    return rule.name, rule.key if rule.status == "team" else None


def display(session, player_ids=None):
    """{player id: {"prefix": label, "team": key or None}} for approved prefixes only."""
    rule_map = rules(session)
    shown = {}
    for player, raw in latest_prefixes(session, player_ids).items():
        found = resolve(rule_map, raw)
        if found:
            shown[player] = dict(prefix=found[0], team=found[1])
    return shown


def attach(session, items, *keys):
    """Add `prefix` (approved label or None) to dicts with a player `id`, like mains."""
    refs = []
    for item in items:
        for key in keys or (None,):
            ref = item.get(key) if key else item
            if ref and ref.get("id"):
                try:
                    refs.append(
                        (ref, ref["id"] if isinstance(ref["id"], UUID) else UUID(ref["id"]))
                    )
                except ValueError:
                    continue
    shown = display(session, {player for _, player in refs}) if refs else {}
    for ref, player in refs:
        ref["prefix"] = (shown.get(player) or {}).get("prefix")


def seen_prefixes(session):
    """Every prefix used at a published tournament, for the organizers' review list."""
    stats = defaultdict(lambda: dict(players=set(), last=None, raw=None))
    for raw, player, starts in session.execute(
        select(TournamentParticipant.prefix, TournamentParticipant.player_id, Tournament.starts_at)
        .join(Tournament, Tournament.id == TournamentParticipant.tournament_id)
        .where(Tournament.published.is_(True), TournamentParticipant.prefix.is_not(None))
    ):
        key = prefix_key(raw)
        if not key:
            continue
        entry = stats[key]
        entry["players"].add(player)
        if starts and (entry["last"] is None or starts > entry["last"]):
            entry["last"], entry["raw"] = starts, clean_prefix(raw)
        entry["raw"] = entry["raw"] or clean_prefix(raw)
    rule_map = rules(session)
    keys = set(stats) | set(rule_map)
    result = []
    for key in keys:
        entry, rule = stats.get(key), rule_map.get(key)
        result.append(
            dict(
                key=key,
                example=(entry or {}).get("raw") or (rule.name if rule else key),
                players=len(entry["players"]) if entry else 0,
                last_seen=entry["last"] if entry else None,
                status=rule.status if rule else None,
                name=rule.name if rule else None,
                team=rule.team if rule else None,
            )
        )
    # Unreviewed first, then by how many players use them.
    return sorted(result, key=lambda r: (r["status"] is not None, -r["players"], r["key"]))


def teams(session, data, team_key=None):
    """Teams with their current members and results in main events of the last year.

    `data` is the insights engine's Data (finishes, ranking order, tags).
    """
    rule_map = rules(session)
    team_rows = [r for r in rule_map.values() if r.status == "team" and team_key in (None, r.key)]
    shown = display(session)
    members = defaultdict(list)
    for player, info in shown.items():
        if info["team"]:
            members[info["team"]].append(player)
    place = {p: i for i, p in enumerate(data.ranked, 1)}
    latest = max((f["starts_at"] for f in data.finishes if f["starts_at"]), default=None)
    since = latest - timedelta(days=365) if latest else None
    result = []
    for row in team_rows:
        people = members.get(row.key, [])
        mine = [
            f
            for f in data.finishes
            if f["player"] in people
            and f.get("main", True)
            and f["starts_at"]
            and since
            and f["starts_at"] >= since
        ]
        titles = [f for f in mine if f["placement"] == 1 and (f["entrants"] or 0) >= 8]
        top8 = [f for f in mine if f["placement"] <= 8 and (f["entrants"] or 0) >= 16]
        roster = sorted(
            (
                dict(
                    id=str(p),
                    tag=data.tags.get(p),
                    ranking=place.get(p),
                    wins=sum(1 for m in data.matches if m.winner == p),
                    losses=sum(1 for m in data.matches if m.loser == p),
                )
                for p in people
            ),
            key=lambda m: (m["ranking"] or 10_000, -m["wins"], (m["tag"] or "").casefold()),
        )
        result.append(
            dict(
                key=row.key,
                name=row.name,
                members=roster,
                titles=len(titles),
                top8=len(top8),
                ranked=sum(1 for m in roster if m["ranking"] and m["ranking"] <= 20),
                results=[
                    dict(
                        id=str(f["player"]),
                        tag=data.tags.get(f["player"]),
                        placement=f["placement"],
                        entrants=f["entrants"],
                        tournament=f["tournament"],
                        tournament_id=f["tournament_id"],
                        date=f["starts_at"].date().isoformat(),
                    )
                    for f in sorted(
                        (f for f in mine if f["placement"] <= 8),
                        key=lambda f: (f["starts_at"], -f["placement"]),
                        reverse=True,
                    )[:20]
                ],
            )
        )
    return sorted(result, key=lambda t: (-t["titles"], -t["ranked"], -t["top8"], t["name"]))
