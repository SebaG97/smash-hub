"""Bracket of an event (Mission 25)."""

import asyncio
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session

from app.brackets import service
from app.competitions.models import Event
from app.integrations.startgg.client import ImportFailure, StartGGClient

router = APIRouter(prefix="/api/v1", tags=["brackets"])
# start.gg did not answer for these events: try again after a while, not on every visit.
RETRY_SECONDS = 600
_failed: dict[UUID, float] = {}


def read_phases(request, session, event):
    """Store the event's phase names from start.gg once (read only); {} when it has none."""
    if event.phases is not None:
        return
    if time.monotonic() - _failed.get(event.id, -RETRY_SECONDS) < RETRY_SECONDS:
        return
    external = service.startgg_event_id(session, event.id)
    if not external:
        event.phases = {}
        session.commit()
        return
    token = request.app.state.settings.startgg_api_token

    async def fetch():
        async with StartGGClient(token) as client:
            return await client.query("event_phases", {"id": external})

    try:
        data = asyncio.run(fetch())
    except ImportFailure:
        _failed[event.id] = time.monotonic()
        return
    event.phases = data
    session.commit()


@router.get("/events/{id}/bracket")
def bracket(request: Request, id: UUID):
    """Phase groups of a published event with every set placed in its column and row."""
    with Session(request.app.state.engine) as s:
        event = s.get(Event, id)
        if event is not None:
            read_phases(request, s, event)
        result = service.event_bracket(s, id)
        if result is None:
            raise HTTPException(404, "Bracket not found")
        return result
