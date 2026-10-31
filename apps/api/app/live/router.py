"""Tournaments being played, read from start.gg with a short cache (Mission 27)."""

import asyncio
import threading
import time

from fastapi import APIRouter, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

from app.insights import preview
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.live import service
from app.players.mains import costumes_by_startgg_player, mains_by_startgg_player
from app.teams import service as teams

router = APIRouter(prefix="/api/v1/live", tags=["live"])
LIST_SECONDS = 120
LIVE_SECONDS = 60  # every visitor shares one reading, whatever the traffic
COUNTRY = "PY"

_list: dict = {"at": -LIST_SECONDS, "items": None}
_events: dict = {}
_busy: dict = {}
_guard = threading.Lock()


def tournaments(request):
    if _list["items"] is not None and time.monotonic() - _list["at"] < LIST_SECONDS:
        return _list["items"]
    now = int(time.time())
    token = request.app.state.settings.startgg_api_token

    async def fetch():
        async with StartGGClient(token) as client:
            return await client.query(
                "live_tournaments",
                {
                    "country": COUNTRY,
                    "videogame": preview.ULTIMATE,
                    "after": now - 4 * 86400,
                    "before": now,
                },
            )

    try:
        data = asyncio.run(fetch())
    except ImportFailure:
        return _list["items"] or []
    items = service.listed((data.get("tournaments") or {}).get("nodes") or [], now)
    _list.update(at=time.monotonic(), items=items)
    return items


def payload(request, slug, event):
    token = request.app.state.settings.startgg_api_token

    async def fetch():
        async with StartGGClient(token) as client:
            return await service.fetch(client, slug, event)

    raw = asyncio.run(fetch())
    people = [
        str(p["player"]["id"])
        for g in raw["groups"]
        for r in g["sets"]
        for s in r.get("slots") or []
        for p in (s.get("entrant") or {}).get("participants") or []
        if (p.get("player") or {}).get("id")
    ]
    with Session(request.app.state.engine) as s:
        rule_map = teams.rules(s)

        def approve(prefix):
            found = teams.resolve(rule_map, prefix) if prefix else None
            return found[0] if found else None

        return service.build(
            raw,
            approve=approve,
            hub=preview.hub_players(s, set(people)),
            known_mains=mains_by_startgg_player(s, set(people)),
            costumes=costumes_by_startgg_player(s, set(people)),
        )


@router.get("")
def live(request: Request):
    """Tournaments in Paraguay under way or that started in the last hours."""
    return {"items": tournaments(request)}


@router.get("/{slug}")
def tournament(
    request: Request,
    slug: str = Path(pattern=r"^[a-z0-9-]{1,120}$"),
    event: str | None = Query(None, pattern=r"^\d{1,12}$"),
):
    """Bracket and standings right now. Only listed tournaments, so nobody can spend the
    start.gg token on arbitrary ones."""
    if not any(t["slug"] == slug for t in tournaments(request)):
        raise HTTPException(404, "Ese torneo no está en vivo")
    key = (slug, event)
    hit = _events.get(key)
    if hit and time.monotonic() - hit[0] < LIVE_SECONDS:
        return hit[1]
    with _guard:
        lock = _busy.setdefault(key, threading.Lock())
    # One reading at a time: the others get the last one instead of queueing on start.gg.
    if not lock.acquire(blocking=hit is None):
        return hit[1] | dict(stale=True)
    try:
        hit = _events.get(key)
        if hit and time.monotonic() - hit[0] < LIVE_SECONDS:
            return hit[1]
        try:
            result = payload(request, slug, event)
        except ImportFailure as exc:
            if hit:
                return hit[1] | dict(stale=True)
            if "not_found" in str(exc):
                raise HTTPException(404, "Ese torneo no está en vivo") from None
            raise HTTPException(502, "start.gg no respondió") from None
        _events[key] = (time.monotonic(), result)
        return result
    finally:
        lock.release()
