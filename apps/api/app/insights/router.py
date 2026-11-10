"""Public insights: badges, records, tournament summaries and the calendar (Mission 13)."""

import asyncio
import time
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

from app.brackets import service as brackets
from app.core import stale
from app.insights import engine, preview, visitors
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.integrations.startgg.images import tournament_images
from app.players.mains import player_mains
from app.players.summary import ranking_place
from app.teams import service as teams

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
CALENDAR_SECONDS = 3600
_calendar = {"at": 0.0, "items": None}
PREVIEW_SECONDS = 900
_previews = {}  # slug -> (monotonic time, start.gg tournament, event, entrants)
VISITOR_SECONDS = 6 * 3600
_visitors = {}  # start.gg player id -> (monotonic time, payload)


def _with_mains(session, items, *keys):
    """Attach the first main and the approved prefix (Mission 22) of every player referenced
    in items (dicts with id/tag)."""
    people = []
    for item in items:
        for key in keys:
            ref = item.get(key) if key else item
            if ref and ref.get("id"):
                people.append(ref)
    ids = list({UUID(p["id"]) for p in people})
    mains = player_mains(session, ids, limit=1)
    prefixes = teams.display(session, ids) if ids else {}
    for p in people:
        p["mains"] = mains.get(UUID(p["id"]), [])
        p["prefix"] = (prefixes.get(UUID(p["id"])) or {}).get("prefix")
    return items


@router.get("/players/{id}")
def player(request: Request, id: UUID):
    with Session(request.app.state.engine) as s:
        data = engine.cached(s)
        if not any(id in (m.winner, m.loser) for m in data.matches) and not any(
            f["player"] == id for f in data.finishes
        ):
            raise HTTPException(404, "Player not found")
        place = (ranking_place(s, id) or {}).get("place")
        return engine.player_insights(data, id, place)


@router.get("/players/{id}/matchups")
def player_matchups(request: Request, id: UUID):
    """Record against each opposing character, from per-game start.gg selections."""
    with Session(request.app.state.engine) as s:
        return {"items": engine.matchups(engine.cached(s), id)}


@router.get("/characters")
def characters(request: Request):
    """Characters played in the scene's singles games and their most frequent players."""
    with Session(request.app.state.engine) as s:
        items = engine.character_stats(engine.cached(s))
        _with_mains(s, [p for item in items for p in item["top_players"]], None)
        return {"items": items, "games": sum(i["games"] for i in items) // 2}


@router.get("/records")
def records(request: Request):
    with Session(request.app.state.engine) as s:
        result = engine.community_records(engine.cached(s))
        for key in ("streaks", "comebacks", "most_active", "titles"):
            _with_mains(s, result[key], None)
        _with_mains(s, result["rivalries"], "a", "b")
        _with_mains(s, result["upsets"], "winner", "loser")
        _month_mains(s, result["player_of_month"])
        return result


def _month_mains(session, month):
    if month:
        _with_mains(session, [r["winner"] for r in month["regions"] if r["winner"]], None)


@router.get("/player-of-month")
def player_of_month(
    request: Request, month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
):
    """Player of the month per region (the latest month with results unless `month`)."""
    with Session(request.app.state.engine) as s:
        data = engine.cached(s)
        if month is not None and month not in engine.months_played(data):
            raise HTTPException(404, "No tournaments that month")
        result = engine.player_of_month(data, month)
        if result is None:
            raise HTTPException(404, "No results yet")
        _month_mains(s, result)
        return result


@router.get("/tournaments/{id}")
def tournament(
    request: Request,
    id: UUID,
    limit: int = Query(8, ge=1, le=16),
    event: UUID | None = None,
):
    """Summary of one singles event of the tournament (its main one unless `event`)."""
    with Session(request.app.state.engine) as s:
        summary = engine.tournament_summary(engine.cached(s), id, limit, event_id=event)
        if summary is None:
            raise HTTPException(404, "Tournament not found")
        _with_mains(s, summary["top"], None)
        _with_mains(s, summary["overperformers"], None)
        _with_mains(s, summary["upsets"], "winner", "loser")
        return summary


def _event(event):
    """The singles event a seeding is made for: its start.gg path and link."""
    if not event or not event.get("slug"):
        return None
    return dict(
        name=event["name"],
        slug=event["slug"],
        url=f"https://www.start.gg/{event['slug']}",
        entrants=event.get("numEntrants"),
    )


@router.get("/calendar")
def calendar(request: Request):
    """Upcoming offline tournaments in Paraguay from start.gg, cached for an hour."""
    if _calendar["items"] is not None and time.monotonic() - _calendar["at"] < CALENDAR_SECONDS:
        return {"items": _calendar["items"]}
    token = request.app.state.settings.startgg_api_token

    async def fetch():
        async with StartGGClient(token) as client:
            return await client.query(
                "upcoming_tournaments", {"country": "PY", "videogame": "1386"}
            )

    try:
        data = asyncio.run(fetch())
    except ImportFailure:
        return {"items": _calendar["items"] or [], "unavailable": True}
    items = [
        dict(
            name=t["name"],
            slug=t["slug"].removeprefix("tournament/"),
            url=f"https://www.start.gg/{t['slug']}",
            starts_at=datetime.fromtimestamp(t["startAt"], UTC).isoformat()
            if t.get("startAt")
            else None,
            city=t.get("city"),
            venue=t.get("venueName"),
            attendees=t.get("numAttendees"),
            images=tournament_images(t.get("images")),
            event=_event(preview.singles_event(t)),
        )
        for t in ((data.get("tournaments") or {}).get("nodes") or [])
        if not t.get("isOnline") and t.get("slug", "").startswith("tournament/")
    ]
    _calendar.update(at=time.monotonic(), items=items)
    return {"items": items}


@router.get("/upcoming/{slug}")
def upcoming(request: Request, slug: str = Path(pattern=r"^[a-z0-9-]{1,120}$")):
    """Preview of an upcoming tournament: entrants from start.gg, the rest from the hub."""
    # Only the start.gg answer is cached: the projection is rebuilt every time, so
    # publishing, unpublishing or moving a seeding shows up right away.
    tournament, event, entrants = _upcoming(request, slug)
    with Session(request.app.state.engine) as s:
        order, source, profiles = preview.projected_order(s, event and event.get("slug"))
        ids = preview.hub_players(s, [e["startgg_player_id"] for e in entrants])
        result = preview.build(
            engine.cached(s),
            tournament=tournament,
            event=event,
            entrants=entrants,
            ids=ids,
            order=order,
            source=source,
            profiles=profiles,
        )
        _with_mains(s, result["entrants"], None)
        # Hub players whose imported sets carry no characters take the seeding's start.gg
        # picks, so the table and the bracket show everyone's character.
        for p in result["entrants"]:
            picks = (profiles.get(p["startgg_player_id"]) or {}).get("mains")
            if not p.get("mains") and picks:
                p["mains"] = picks[:1]
    # Mission 25: start.gg's first phase (pools or the bracket) with the hub's published
    # seeds in it; never with start.gg's own seeds.
    result["bracket"] = (
        brackets.projection(token_of(request), event["id"], result["entrants"])
        if source["source"] == "seeding" and event
        else None
    )
    return result


def _upcoming(request, slug):
    """start.gg's tournament, singles event and entrants, refreshed every PREVIEW_SECONDS.

    Once a preview loaded, a stale copy answers right away while start.gg is asked again in
    the background, so the page stays up when start.gg is slow or down.
    """
    token = request.app.state.settings.startgg_api_token

    def load():
        async def fetch():
            async with StartGGClient(token) as client:
                return await preview.fetch(client, slug)

        return asyncio.run(fetch())

    try:
        return stale.cached(_previews, slug, PREVIEW_SECONDS, load)
    except ImportFailure as exc:
        if "not_found" in str(exc):
            raise HTTPException(404, "Tournament not found") from None
        raise HTTPException(502, "start.gg did not answer") from None


@router.get("/upcoming/{slug}/pools")
def upcoming_pools(request: Request, slug: str = Path(pattern=r"^[a-z0-9-]{1,120}$")):
    """The published seeding laid on start.gg's pools, for readers (read only)."""
    from app.seeding import pools
    from app.seeding import service as seeding

    _, event, _ = _upcoming(request, slug)
    with Session(request.app.state.engine) as s:
        project = preview.published_seeding(s, event and event.get("slug"))
        if project is None:
            raise HTTPException(404, "No published seeding")
        try:
            found = pools.read_public(token_of(request), project.startgg_event_slug)
        except ImportFailure:
            raise HTTPException(502, "start.gg did not answer") from None
        if not found or not found["seeds"]:
            raise HTTPException(404, "start.gg has no pools yet")
        _, rows = seeding.final_seeding(s, project)
        seeding._public_prefixes(s, rows, rows)
        seeding.with_countries(s, rows)
        ids = preview.hub_players(s, [r["player_id"] for r in rows])
        return preview.public_pools(pools.build(rows, found), ids)


def token_of(request):
    return request.app.state.settings.startgg_api_token


@router.get("/startgg-players/{player_id}")
def startgg_player(request: Request, player_id: str = Path(pattern=r"^\d{1,20}$")):
    """A year of start.gg results for an entrant the hub has no data for (read only)."""
    hit = _visitors.get(player_id)
    if hit and time.monotonic() - hit[0] < VISITOR_SECONDS:
        return hit[1]
    token = request.app.state.settings.startgg_api_token

    async def fetch():
        async with StartGGClient(token) as client:
            return await visitors.fetch(client, player_id)

    try:
        result = asyncio.run(fetch())
    except ImportFailure as exc:
        if "not_found" in str(exc):
            raise HTTPException(404, "Player not found") from None
        raise HTTPException(502, "start.gg did not answer") from None
    _visitors[player_id] = (time.monotonic(), result)
    return result
