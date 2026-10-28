"""Preview of an upcoming tournament (Mission 16).

Entrants come from start.gg (read only); everything else from the hub's imported results:
the official seeds, favorites and likely top-8 crossings with their head-to-head (only once
the hub's seeding of the event is published), who is on a streak, the bracket's classic
rivalries and first-timers.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.insights import engine
from app.integrations.startgg.client import ImportFailure
from app.integrations.startgg.images import tournament_images
from app.players.models import ExternalIdentity
from app.seeding import startgg as seeding_startgg

ULTIMATE = "1386"
RECENT_DAYS = 60
# Winners-side top 8 of a double-elimination bracket if the seeds hold.
CROSSINGS = [
    ("Cuartos de winners", 1, 8),
    ("Cuartos de winners", 4, 5),
    ("Cuartos de winners", 2, 7),
    ("Cuartos de winners", 3, 6),
    ("Semifinal de winners", 1, 4),
    ("Semifinal de winners", 2, 3),
    ("Final de winners", 1, 2),
]


def singles_event(tournament):
    """The offline Ultimate singles event with the most entrants, or None."""
    events = [
        e
        for e in tournament.get("events") or []
        if str((e.get("videogame") or {}).get("id")) == ULTIMATE
        and not e.get("isOnline")
        and ((e.get("teamRosterSize") or {}).get("maxPlayers") or 1) <= 1
    ]
    return max(events, key=lambda e: e.get("numEntrants") or 0, default=None)


async def fetch(client, slug):
    """Tournament, its singles event and the entrants, straight from start.gg."""
    tournament = (await client.query("upcoming_tournament", {"slug": slug})).get("tournament")
    if not tournament:
        raise ImportFailure("startgg_tournament_not_found")
    event = singles_event(tournament)
    entrants = await seeding_startgg.fetch_entrants(client, event["id"]) if event else []
    return tournament, event, entrants


def projected_order(session, event_slug):
    """{start.gg player id: seed} and where it comes from.

    Only a published seeding of this very event counts: without one the preview shows no
    seeds at all, so readers never mistake a projection for the official bracket.
    """
    from app.seeding import service
    from app.seeding.models import SeedingProject

    published = select(SeedingProject).where(
        SeedingProject.published.is_(True), SeedingProject.current_run_id.is_not(None)
    )
    seeding = (
        session.scalar(
            published.where(
                SeedingProject.kind == "seeding",
                SeedingProject.startgg_event_slug == event_slug,
            )
        )
        if event_slug
        else None
    )
    if seeding is not None:
        _, rows = service.final_seeding(session, seeding)
        return {r["player_id"]: r["seed"] for r in rows}, dict(
            source="seeding", label=f"Seeding oficial publicado ({seeding.name})"
        )
    return {}, dict(source="none", label="Todavía no hay un seeding oficial publicado")


def hub_players(session, startgg_ids):
    """{start.gg player id: hub player id}."""
    external = {f"player:{pid}": pid for pid in startgg_ids}
    return {
        external[ext]: player
        for ext, player in session.execute(
            select(ExternalIdentity.external_id, ExternalIdentity.player_id).where(
                ExternalIdentity.external_id.in_(list(external))
            )
        ).all()
    }


def form(data, player):
    """Overall and recent set record plus the current streak, from hub results."""
    mine = [m for m in data.matches if player in (m.winner, m.loser)]
    wins = sum(m.winner == player for m in mine)
    since = data.matches[-1].at - timedelta(days=RECENT_DAYS) if data.matches else None
    recent = [m for m in mine if since and m.at >= since]
    _, current, _ = engine.streaks(mine, player)
    return dict(
        wins=wins,
        losses=len(mine) - wins,
        recent_wins=sum(m.winner == player for m in recent),
        recent_losses=sum(m.loser == player for m in recent),
        streak=current,
    )


def head_to_head(data, a, b):
    sets = [m for m in data.matches if {m.winner, m.loser} == {a, b}]
    if not sets:
        return None
    last = sets[-1]
    return dict(
        a_wins=sum(m.winner == a for m in sets),
        b_wins=sum(m.winner == b for m in sets),
        last=dict(
            tournament=last.tournament,
            tournament_id=last.tournament_id,
            date=last.at.date().isoformat(),
            winner=data.tags.get(last.winner),
        ),
    )


def build(data, *, tournament, event, entrants, ids, order, source):
    """The preview payload; pure so it can be tested without start.gg or a database."""
    stats = {
        sgg: form(data, ids[sgg])
        for sgg in (e["startgg_player_id"] for e in entrants)
        if sgg in ids
    }
    official = source["source"] == "seeding"
    unranked = len(order) + 1
    rows = sorted(
        entrants,
        key=lambda e: (
            order.get(e["startgg_player_id"], unranked),
            -(stats.get(e["startgg_player_id"]) or {}).get("wins", 0),
            e["gamer_tag"].lower(),
        ),
    )
    people = []
    for place, e in enumerate(rows, 1):
        player = ids.get(e["startgg_player_id"])
        people.append(
            dict(
                seed=place if official else None,
                tag=e["gamer_tag"],
                id=str(player) if player else None,
                startgg_player_id=e["startgg_player_id"],
                ranked=e["startgg_player_id"] in order,
                **(stats.get(e["startgg_player_id"]) or {}),
            )
        )
    position = {p["startgg_player_id"]: place for place, p in enumerate(people)}
    by_seed = {p["seed"]: p for p in people if p["seed"]}
    crossings = []
    for stage, a, b in CROSSINGS if official else ():
        pa, pb = by_seed.get(a), by_seed.get(b)
        if not pa or not pb or len(people) < 8:
            continue
        h2h = head_to_head(data, ids_of(pa), ids_of(pb)) if pa["id"] and pb["id"] else None
        crossings.append(dict(stage=stage, a=ref(pa), b=ref(pb), h2h=h2h))
    hub = {p["id"]: p for p in people if p["id"]}
    pairs = Counter(
        frozenset((str(m.winner), str(m.loser)))
        for m in data.matches
        if str(m.winner) in hub and str(m.loser) in hub
    )
    shown = {frozenset((c["a"]["id"], c["b"]["id"])) for c in crossings}
    rivalries = []
    for pair, n in pairs.most_common():
        if n < 3 or len(rivalries) == 5:
            break
        if pair in shown:
            continue
        a, b = sorted((hub[x] for x in pair), key=lambda p: position[p["startgg_player_id"]])
        h2h = head_to_head(data, ids_of(a), ids_of(b))
        rivalries.append(dict(a=ref(a), b=ref(b), sets=n, h2h=h2h))
    on_fire = sorted(
        (p for p in people if p.get("streak", 0) >= 3),
        key=lambda p: (-p["streak"], position[p["startgg_player_id"]]),
    )[:5]
    newcomers = [p for p in people if not p.get("wins") and not p.get("losses")]
    return dict(
        tournament=dict(
            name=tournament["name"],
            slug=tournament["slug"].removeprefix("tournament/"),
            url=f"https://www.start.gg/{tournament['slug']}",
            starts_at=datetime.fromtimestamp(tournament["startAt"], UTC).isoformat()
            if tournament.get("startAt")
            else None,
            city=tournament.get("city"),
            venue=tournament.get("venueName"),
            attendees=tournament.get("numAttendees"),
            images=tournament_images(tournament.get("images")),
        ),
        event=dict(name=event["name"], entrants=len(entrants)) if event else None,
        seeding=source,
        entrants=people,
        favorites=people[:4] if official else [],
        on_fire=on_fire,
        crossings=crossings,
        rivalries=rivalries,
        newcomers=dict(count=len(newcomers), tags=[p["tag"] for p in newcomers[:12]]),
    )


def ids_of(person):
    return UUID(person["id"])


def ref(person):
    return dict(id=person["id"], tag=person["tag"], seed=person["seed"])
