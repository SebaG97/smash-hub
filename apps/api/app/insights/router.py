"""Public insights: badges, records, tournament summaries and the calendar (Mission 13)."""

import asyncio
import time
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

from app.insights import engine, preview, visitors
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.players.mains import player_mains
from app.players.summary import ranking_place

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
CALENDAR_SECONDS = 3600
_calendar = {"at": 0.0, "items": None}
PREVIEW_SECONDS = 900
_previews = {}  # slug -> (monotonic time, start.gg tournament, event, entrants)
VISITOR_SECONDS = 6 * 3600
_visitors = {}  # start.gg player id -> (monotonic time, payload)


def _with_mains(session, items, *keys):
    """Attach the first main of every player referenced in items (dicts with id/tag)."""
    people = []
    for item in items:
        for key in keys:
            ref = item.get(key) if key else item
            if ref and ref.get("id"):
                people.append(ref)
    mains = player_mains(session, list({UUID(p["id"]) for p in people}), limit=1)
    for p in people:
        p["mains"] = mains.get(UUID(p["id"]), [])
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
        if result["player_of_month"]:
            _with_mains(s, [result["player_of_month"]], None)
        return result


@router.get("/tournaments/{id}")
def tournament(request: Request, id: UUID, limit: int = Query(8, ge=1, le=16)):
    with Session(request.app.state.engine) as s:
        summary = engine.tournament_summary(engine.cached(s), id, limit)
        if summary is None:
            raise HTTPException(404, "Tournament not found")
        _with_mains(s, summary["top"], None)
        _with_mains(s, summary["overperformers"], None)
        _with_mains(s, summary["upsets"], "winner", "loser")
        return summary


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
    hit = _previews.get(slug)
    if hit and time.monotonic() - hit[0] < PREVIEW_SECONDS:
        tournament, event, entrants = hit[1]
    else:
        token = request.app.state.settings.startgg_api_token

        async def fetch():
            async with StartGGClient(token) as client:
                return await preview.fetch(client, slug)

        try:
            tournament, event, entrants = asyncio.run(fetch())
        except ImportFailure as exc:
            if "not_found" in str(exc):
                raise HTTPException(404, "Tournament not found") from None
            raise HTTPException(502, "start.gg did not answer") from None
        _previews[slug] = (time.monotonic(), (tournament, event, entrants))
    with Session(request.app.state.engine) as s:
        order, source = preview.projected_order(s, event and event.get("slug"))
        ids = preview.hub_players(s, [e["startgg_player_id"] for e in entrants])
        result = preview.build(
            engine.cached(s),
            tournament=tournament,
            event=event,
            entrants=entrants,
            ids=ids,
            order=order,
            source=source,
        )
        _with_mains(s, result["entrants"], None)
    return result


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
