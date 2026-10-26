"""Seeding routes. Reads are public; every write requires the admin key and is audited."""

import hmac
import re
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.seeding import service
from app.seeding.engine import Method, Parameters
from app.seeding.models import SeedingProject

router = APIRouter(prefix="/api/v1/seeding", tags=["seeding"])

FAILURE_WINDOW, FAILURE_LIMIT = 600, 10
_failures: dict[str, deque] = defaultdict(deque)


def admin(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_admin_name: Annotated[str | None, Header()] = None,
) -> str:
    """Shared admin key (ADR-011). Returns the actor name recorded in the audit log."""
    secret = request.app.state.settings.admin_token
    if secret is None:
        raise HTTPException(503, "La edición está deshabilitada: falta ADMIN_TOKEN en la API.")
    client = request.client.host if request.client else "?"
    now = time.monotonic()
    recent = _failures[client]
    while recent and now - recent[0] > FAILURE_WINDOW:
        recent.popleft()
    if len(recent) >= FAILURE_LIMIT:
        raise HTTPException(429, "Demasiados intentos fallidos; espera unos minutos.")
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not given or not hmac.compare_digest(given.encode(), secret.get_secret_value().encode()):
        recent.append(now)
        raise HTTPException(401, "Clave de administración incorrecta.")
    name = re.sub(r"[^\w .@-]", "", x_admin_name or "", flags=re.UNICODE).strip()[:60]
    return name or "admin"


Admin = Annotated[str, Depends(admin)]


def session_for(request):
    return Session(request.app.state.engine, expire_on_commit=False)


def run(request, operation, *args, write=False):
    with session_for(request) as session:
        try:
            result = operation(session, *args)
            if write:
                session.commit()
            return result
        except service.ProjectNotFound:
            raise HTTPException(404, "Seeding no encontrado") from None
        except service.InvalidRequest as exc:
            raise HTTPException(422, str(exc)) from None


class RecalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window_start: AwareDatetime | None = None
    window_end: AwareDatetime | None = None
    refresh: bool = False
    parameters: Parameters | None = None
    # Shortcut: keep the current parameters and only change the official method.
    method: Method | None = None


class OverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int = Field(ge=1, le=4096)
    reason: str = Field(min_length=3, max_length=300)


@router.get("")
def projects(request: Request, kind: Literal["seeding", "ranking"] | None = None):
    query = select(SeedingProject).order_by(SeedingProject.event_date.desc())
    if kind is not None:
        query = query.where(SeedingProject.kind == kind)
    with session_for(request) as session:
        return [
            dict(
                slug=p.slug,
                name=p.name,
                kind=p.kind,
                country_code=p.country_code,
                event_date=p.event_date,
                window_start=p.window_start,
            )
            for p in session.scalars(query)
        ]


@router.get("/{slug}")
def project_view(request: Request, slug: str):
    return run(request, lambda s: service.view(s, service.project_by_slug(s, slug)))


@router.get("/{slug}/export.csv")
def export(request: Request, slug: str):
    body = run(request, lambda s: service.export_csv(s, service.project_by_slug(s, slug)))
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="seeding-{slug}.csv"'},
    )


@router.get("/{slug}/audit")
def audit(request: Request, slug: str, actor: Admin):
    return run(request, lambda s: service.audit_log(s, service.project_by_slug(s, slug)))


@router.post("/{slug}/recalculate", status_code=200)
def recalculate(
    request: Request, slug: str, body: RecalculateRequest, actor: Admin, response: Response
):
    if body.refresh:
        try:
            service.start_refresh(
                request.app.state.engine,
                slug,
                actor,
                request.app.state.settings.startgg_api_token,
                body.window_start,
                method=body.method,
            )
        except service.ProjectNotFound:
            raise HTTPException(404, "Seeding no encontrado") from None
        except service.InvalidRequest as exc:
            raise HTTPException(422, str(exc)) from None
        except service.RefreshBusy:
            raise HTTPException(409, "Ya hay una descarga de start.gg en curso.") from None
        response.status_code = 202
        return {"status": "refreshing"}

    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        if project.refresh_status == "RUNNING":
            raise service.InvalidRequest("Espera a que termine la descarga de start.gg.")
        service.recalculate(
            session,
            project,
            actor,
            window_start=body.window_start,
            window_end=body.window_end,
            parameters=body.parameters,
            method=body.method,
        )
        return {"status": "recalculated"}

    return run(request, operation, write=True)


@router.put("/{slug}/overrides/{player_id}")
def move(request: Request, slug: str, player_id: str, body: OverrideRequest, actor: Admin):
    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        service.set_override(session, project, player_id, body.seed, body.reason.strip(), actor)
        return {"status": "moved"}

    return run(request, operation, write=True)


@router.delete("/{slug}/overrides/{player_id}")
def reset(request: Request, slug: str, player_id: str, actor: Admin):
    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        if not service.clear_override(session, project, player_id, actor):
            raise service.InvalidRequest("Ese jugador no tiene un ajuste manual.")
        return {"status": "reset"}

    return run(request, operation, write=True)


@router.get("/{slug}/session")
def check_key(request: Request, slug: str, actor: Admin):
    """Lets the page validate the admin key without changing anything."""
    return {"actor": actor, "at": datetime.now().astimezone().isoformat()}
