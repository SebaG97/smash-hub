"""Bracket of an event (Mission 25)."""

import asyncio
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session

from app.brackets import service
from app.competitions.models import Event
from app.core.admin import Admin
from app.insights import preview
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.seeding import service as seeding
from app.seeding import startgg as seeding_startgg

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


@router.get("/seeding/{slug}/bracket")
def seeding_bracket(request: Request, slug: str, actor: Admin):
    """Organizers only: how start.gg's bracket (pools included) looks with this seeding,
    published or not. Nothing is written to start.gg."""
    token = request.app.state.settings.startgg_api_token
    with Session(request.app.state.engine) as s:
        try:
            project = seeding.project_by_slug(s, slug)
        except seeding.ProjectNotFound:
            raise HTTPException(404, "Seeding no encontrado") from None
        if project.kind != "seeding" or not project.startgg_event_slug:
            raise HTTPException(422, "Solo los seedings de un evento de start.gg tienen bracket.")
        _, rows = seeding.final_seeding(s, project)
        if not rows:
            raise HTTPException(422, "Todavía no hay un cálculo de este seeding.")
        hub = preview.hub_players(s, [r["player_id"] for r in rows])
        people = [
            dict(
                seed=r["seed"],
                tag=r["gamer_tag"],
                id=str(hub[r["player_id"]]) if r["player_id"] in hub else None,
                mains=r.get("mains") or [],
            )
            for r in rows
        ]
        seeding._public_prefixes(s, rows, people)
        slug_of_event = project.startgg_event_slug

    async def fetch():
        async with StartGGClient(token) as client:
            return await seeding_startgg.fetch_event(client, slug_of_event)

    try:
        event = asyncio.run(fetch())
    except ImportFailure:
        raise HTTPException(502, "start.gg no respondió") from None
    result = service.projection(token, event["id"], people)
    if result is None:
        raise HTTPException(422, "Hacen falta al menos 4 jugadores con seed.")
    return result | dict(published=project.published)
