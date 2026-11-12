"""Administrators' view of the start.gg sync and its manual trigger (ADR-022)."""

import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.admin import Admin
from app.core.times import LOCAL_PATTERN, from_asuncion, to_asuncion
from app.integrations.startgg.client import ImportFailure, parse_slug
from app.sync import service

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])
BUSY = {
    "sync": "Ya hay una sincronización con start.gg en curso; probá en unos minutos.",
    "seeding": "Hay una descarga de seeding en curso; probá cuando termine.",
    "importer": "Hay una importación de torneos en curso; probá cuando termine.",
}


class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Link or slug of the start.gg tournament.
    tournament: str = Field(min_length=1, max_length=300)


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Date and time in Asunción ("2026-11-14T14:00"); null goes back to start.gg's.
    starts_at: str | None = Field(default=None, pattern=LOCAL_PATTERN)


class TrackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tracked: bool


def _token(request):
    token = request.app.state.settings.startgg_api_token
    if token is None or not token.get_secret_value().strip():
        raise HTTPException(422, "La API no tiene STARTGG_API_TOKEN configurado.")


def _start(target, *args):
    """Run in the background (tests replace this to run inline)."""
    threading.Thread(target=target, args=args, daemon=True, name="startgg-sync-manual").start()


@router.get("")
def sync_status(request: Request, actor: Admin):
    """Tracked tournaments with their last and next sync, and the latest runs."""
    with Session(request.app.state.engine) as s:
        return service.status(s) | dict(enabled=request.app.state.settings.startgg_sync_enabled)


@router.post("/tournaments", status_code=202)
def sync_tournament(request: Request, body: SyncRequest, actor: Admin):
    """Sync one tournament now (and track it from then on)."""
    _token(request)
    try:
        slug = parse_slug(body.tournament)
    except ImportFailure:
        raise HTTPException(422, "Pegá el link o el slug del torneo de start.gg.") from None
    engine, settings = request.app.state.engine, request.app.state.settings
    try:
        run_id = service.claim(engine, kind="tournament", trigger="manual", actor=actor, slug=slug)
    except service.SyncBusy as busy:
        raise HTTPException(409, BUSY.get(str(busy), BUSY["sync"])) from None
    _start(service.run_tournament, engine, settings, run_id, slug)
    return {"status": "started", "run_id": str(run_id), "slug": slug}


@router.post("/discover", status_code=202)
def discover(request: Request, actor: Admin):
    """Look for the country's upcoming tournaments on start.gg now."""
    _token(request)
    engine, settings = request.app.state.engine, request.app.state.settings
    try:
        run_id = service.claim(engine, kind="discovery", trigger="manual", actor=actor)
    except service.SyncBusy as busy:
        raise HTTPException(409, BUSY.get(str(busy), BUSY["sync"])) from None
    _start(service.run_discovery, engine, settings, run_id)
    return {"status": "started", "run_id": str(run_id)}


@router.put("/tournaments/{slug}/tracking")
def tracking(request: Request, slug: str, body: TrackRequest, actor: Admin):
    """Stop (or resume) syncing a tournament on schedule. Its data stays."""
    with Session(request.app.state.engine) as s:
        row = service.set_tracked(s, slug, body.tracked)
        if row is None:
            raise HTTPException(404, "Ese torneo no está en la copia local.")
        s.commit()
        return {"slug": slug, "tracked": row.tracked}


@router.put("/tournaments/{slug}/start")
def confirm_start(request: Request, slug: str, body: StartRequest, actor: Admin):
    """Confirm the real start (Asunción time) when start.gg's is wrong. start.gg's value
    is kept; the schedule, previews and Prodes opened afterwards use this one."""
    try:
        start = from_asuncion(body.starts_at) if body.starts_at else None
    except ValueError:
        raise HTTPException(422, "Fecha u hora inválida.") from None
    with Session(request.app.state.engine) as s:
        row = service.confirm_start(s, slug, start, actor, request.app.state.settings)
        if row is None:
            raise HTTPException(404, "Ese torneo no está en la copia local.")
        s.commit()
        return {
            "slug": slug,
            "starts_at": to_asuncion(service.starts_at(row)),
            "confirmed": row.start_confirmed_at is not None,
            "tier": service.tier(row, service.now_utc()),
        }
