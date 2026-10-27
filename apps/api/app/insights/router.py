"""Public insights: badges, records, tournament summaries and the calendar (Mission 13)."""

import asyncio
import time
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.insights import engine
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.players.mains import player_mains
from app.players.summary import ranking_place

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
CALENDAR_SECONDS = 3600
_calendar = {"at": 0.0, "items": None}


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
