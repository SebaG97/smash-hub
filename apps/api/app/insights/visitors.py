"""Recent start.gg results of entrants the hub has no data for (Mission 18).

Foreign players (and locals who never played an imported tournament) are read straight
from start.gg on demand: a year of in-person singles sets, their tournaments and mains.
Read only, like the seeding's own queries.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta

from app.seeding import startgg as seeding_startgg

ULTIMATE = "1386"
WINDOW_DAYS = 365


async def fetch(client, player_id, now=None):
    end = now or datetime.now(UTC)
    start = end - timedelta(days=WINDOW_DAYS)
    nodes = await seeding_startgg.fetch_player_sets(client, player_id, start)
    mains = await seeding_startgg.fetch_player_mains(client, player_id, ULTIMATE)
    return summarize(nodes, player_id, start=start, end=end, mains=mains)


def summarize(nodes, player_id, *, start, end, mains):
    """Record, tournaments, best results, home country and mains from provider sets."""
    rows, _ = seeding_startgg.normalize(
        nodes, videogame_id=ULTIMATE, own_event_id=None, start=start, end=end
    )
    player_id = str(player_id)
    mine = [
        r for r in rows if not r["online"] and player_id in (r["p1_player_id"], r["p2_player_id"])
    ]
    played = [r for r in mine if r["counted"]]
    wins = sum(r["winner_player_id"] == player_id for r in played)
    events, tags, countries = {}, Counter(), Counter()
    for r in mine:
        side = "p1" if r["p1_player_id"] == player_id else "p2"
        tags[r[f"{side}_tag"]] += 1
        event = events.setdefault(
            r["startgg_event_id"],
            dict(
                tournament=r["tournament_name"],
                url=f"https://www.start.gg/{r['tournament_slug']}"
                if r["tournament_slug"]
                else None,
                entrants=r["event_entrants"],
                placement=None,
                date=r["played_at"],
                country=r["country"],
            ),
        )
        event["placement"] = event["placement"] or r[f"{side}_placement"]
        event["date"] = max(event["date"], r["played_at"])
    for event in events.values():
        if event["country"]:
            countries[event["country"]] += 1
    ordered = sorted(events.values(), key=lambda e: e["date"], reverse=True)
    best = sorted(
        (e for e in ordered if e["placement"]),
        key=lambda e: (e["placement"], -(e["entrants"] or 0)),
    )

    def view(e):
        return dict(e, date=e["date"].date().isoformat())

    return dict(
        player_id=player_id,
        tag=tags.most_common(1)[0][0] if tags else None,
        country=countries.most_common(1)[0][0] if countries else None,
        since=start.date().isoformat(),
        wins=wins,
        losses=len(played) - wins,
        tournaments=len(events),
        recent=[view(e) for e in ordered[:5]],
        best=[view(e) for e in best[:3]],
        mains=mains,
    )
