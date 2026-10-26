"""start.gg access for seeding: read the entrants' set history and write a phase's seeds.

Reads run from the API's background refresh; the single write (updatePhaseSeeding) is only
reachable from the operator CLI, never from HTTP.
"""

import re
from datetime import UTC, datetime

from app.integrations.startgg.client import ImportFailure

PER_PAGE = 25  # ~28 objects per set; 30 once exceeded start.gg's 1000-object limit
MAX_PAGES = 80


async def paged(
    client, document, root, connection, variables, *, per_page=PER_PAGE, max_pages=MAX_PAGES
):
    nodes, seen, expected = [], set(), None
    for page in range(1, max_pages + 1):
        data = await client.query(document, {**variables, "page": page, "perPage": per_page})
        try:
            holder = data[root]
            if holder is None:
                raise ImportFailure(f"startgg_{root}_not_found")
            conn = holder[connection]
            info = conn["pageInfo"]
            total, pages = info["total"], info["totalPages"]
            if expected is None:
                expected = total
            for node in conn["nodes"] or []:
                if str(node["id"]) not in seen:
                    seen.add(str(node["id"]))
                    nodes.append(node)
        except (KeyError, TypeError):
            raise ImportFailure("startgg_invalid_response") from None
        if page >= (pages or 0):
            return nodes
    raise ImportFailure("startgg_pagination_limit")


async def fetch_event(client, slug):
    event = (await client.query("seeding_event", {"slug": slug})).get("event")
    if not event:
        raise ImportFailure("startgg_event_not_found")
    return event


async def fetch_entrants(client, event_id):
    rows = []
    for node in await paged(
        client, "seeding_entrants", "event", "entrants", {"id": event_id}, per_page=40
    ):
        parts = node.get("participants") or []
        if len(parts) != 1 or not (parts[0].get("player") or {}).get("id"):
            raise ImportFailure("startgg_entrant_not_singles")
        part = parts[0]
        rows.append(
            dict(
                startgg_entrant_id=str(node["id"]),
                startgg_player_id=str(part["player"]["id"]),
                gamer_tag=(part.get("gamerTag") or node["name"])[:120],
                prefix=(part.get("prefix") or None),
                profile_country=((part.get("user") or {}).get("location") or {}).get("country"),
            )
        )
    return rows


async def fetch_player_sets(client, player_id, after):
    return await paged(
        client,
        "seeding_player_sets",
        "player",
        "sets",
        {"id": player_id, "after": int(after.timestamp())},
    )


def _side(slot):
    entrant = slot.get("entrant")
    if not entrant:
        return None
    score = (((slot.get("standing") or {}).get("stats") or {}).get("score") or {}).get("value")
    return dict(
        entrant_id=str(entrant["id"]),
        name=entrant.get("name") or "",
        player_ids=[
            str((p.get("player") or {}).get("id")) for p in entrant.get("participants") or []
        ],
        placement=(entrant.get("standing") or {}).get("placement"),
        score=score,
    )


def classify(node, sides):
    """Same rules as statistics eligibility (ADR-009/010) for provider sets."""
    if node.get("hasPlaceholder"):
        return "placeholder"
    if len(sides) < 2:
        return "bye"
    if node.get("state") != 3:
        return "not_played"
    ids = {s["entrant_id"] for s in sides}
    if len(ids) != 2 or node.get("winnerId") is None or str(node["winnerId"]) not in ids:
        return "no_valid_winner"
    scores = [s["score"] for s in sides]
    if "DQ" in (node.get("displayScore") or "").upper() or any(
        v is not None and v < 0 for v in scores
    ):
        return "dq"
    if all(v is None for v in scores):
        return "played_unscored"
    if any(v is None for v in scores):
        return "inconsistent_score"
    win = next(s for s in sides if s["entrant_id"] == str(node["winnerId"]))
    lose = next(s for s in sides if s is not win)
    return "played" if win["score"] > lose["score"] else "inconsistent_score"


COUNTED = {"played", "played_unscored"}


def normalize(nodes, *, videogame_id, own_event_id, start, end):
    """Provider set nodes -> SeedingSet rows (deduplicated). Returns (rows, excluded counter dict)."""
    rows, excluded = {}, {}
    for node in nodes:
        sid = str(node["id"])
        if sid in rows:
            continue
        event = node.get("event") or {}
        tournament = event.get("tournament") or {}
        ts = node.get("completedAt") or node.get("startedAt") or event.get("startAt")
        reason = None
        if str((event.get("videogame") or {}).get("id")) != str(videogame_id):
            reason = "other_game"
        elif str(event.get("id")) == str(own_event_id):
            reason = "seeded_event"
        elif not ts or not start <= datetime.fromtimestamp(ts, UTC) < end:
            reason = "outside_window"
        sides = [s for s in (_side(slot) for slot in node.get("slots") or []) if s]
        if reason is None and any(len(s["player_ids"]) != 1 for s in sides):
            reason = "not_singles"
        if reason:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        cls = classify(node, sides)
        if re.match(r"tournament/test", tournament.get("slug") or "") and cls in COUNTED:
            cls = "excluded_test_event"
        p1 = sides[0] if sides else None
        p2 = sides[1] if len(sides) > 1 else None
        winner = next(
            (s["player_ids"][0] for s in sides if s["entrant_id"] == str(node.get("winnerId"))),
            None,
        )
        rows[sid] = dict(
            startgg_set_id=sid,
            played_at=datetime.fromtimestamp(ts, UTC),
            startgg_event_id=str(event["id"]),
            tournament_name=(tournament.get("name") or "?")[:300],
            tournament_slug=tournament.get("slug"),
            event_entrants=event.get("numEntrants"),
            online=bool(event.get("isOnline")),
            country=(tournament.get("countryCode") or None),
            p1_player_id=p1["player_ids"][0] if p1 else None,
            p1_tag=p1["name"][:200] if p1 else None,
            p1_placement=p1["placement"] if p1 else None,
            p2_player_id=p2["player_ids"][0] if p2 else None,
            p2_tag=p2["name"][:200] if p2 else None,
            p2_placement=p2["placement"] if p2 else None,
            winner_player_id=winner,
            classification=cls,
            counted=cls in COUNTED,
        )
    return list(rows.values()), excluded


async def fetch_phase_seeds(client, phase_id):
    return await paged(
        client, "seeding_phase_seeds", "phase", "seeds", {"id": phase_id}, per_page=50
    )


async def update_phase_seeding(client, phase_id, mapping):
    """mapping: [{"seedId": str, "seedNum": int}]. Writes to start.gg."""
    data = await client.query("seeding_update_phase", {"phaseId": phase_id, "seedMapping": mapping})
    if not data.get("updatePhaseSeeding"):
        raise ImportFailure("startgg_seeding_rejected")
    return data["updatePhaseSeeding"]
