"""Seeding routes. Reads are public; every write requires the admin key and is audited."""

import asyncio
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.admin import Admin, MaybeAdmin
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.seeding import pools, push, service, startgg
from app.seeding.engine import Method, Parameters
from app.seeding.models import SeedingProject

router = APIRouter(prefix="/api/v1/seeding", tags=["seeding"])


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
    # Also drop manual moves, so every player goes back to the calculated place.
    reset_overrides: bool = False


class OverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int = Field(ge=1, le=4096)
    reason: str = Field(min_length=3, max_length=300)


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["seeding", "ranking"]
    name: str = Field(min_length=3, max_length=200)
    slug: str | None = Field(default=None, max_length=80)
    # Seeding: link or path of the start.gg event. Ranking: ISO country code.
    event_url: str | None = Field(default=None, max_length=400)
    country: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    window_start: AwareDatetime
    end: AwareDatetime
    download: bool = True


class MergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_player_id: str = Field(pattern=r"^\d{1,20}$")
    to_player_id: str = Field(pattern=r"^\d{1,20}$")


class DuplicateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: str = Field(pattern=r"^\d{1,20}$")
    keep_player_id: str = Field(pattern=r"^\d{1,20}$")


@router.get("/session")
def check_admin(actor: Admin):
    """Validates the admin key from list pages, where there is no project yet."""
    return {"actor": actor}


@router.post("", status_code=201)
def create(request: Request, body: CreateRequest, actor: Admin):
    token = request.app.state.settings.startgg_api_token
    event = None
    if body.kind == "seeding":
        try:
            path = service.event_path(body.event_url)
        except service.InvalidRequest as exc:
            raise HTTPException(422, str(exc)) from None

        async def lookup():
            async with StartGGClient(token) as client:
                return await startgg.fetch_event(client, path)

        try:
            event = asyncio.run(lookup())
        except ImportFailure as exc:
            detail = {
                "startgg_token_missing": "La API no tiene STARTGG_API_TOKEN configurado.",
                "startgg_event_not_found": "start.gg no encontró ese evento.",
            }.get(str(exc), "No se pudo consultar start.gg; intenta de nuevo.")
            raise HTTPException(422, detail) from None
    elif not body.country:
        raise HTTPException(422, "Indica el país del ranking (por ejemplo PY).")

    def operation(session):
        project = service.create_project(
            session,
            actor,
            kind=body.kind,
            name=body.name,
            slug=body.slug,
            window_start=body.window_start,
            end=body.end,
            event=event,
            country=body.country,
        )
        return project.slug

    with session_for(request) as session:
        try:
            slug = operation(session)
            session.commit()
        except service.SlugTaken:
            raise HTTPException(409, "Ya existe uno con ese nombre corto; elige otro.") from None
        except service.InvalidRequest as exc:
            raise HTTPException(422, str(exc)) from None
    started = False
    if body.download and token is not None and token.get_secret_value().strip():
        service.start_refresh(request.app.state.engine, slug, actor, token)
        started = True
    return {"slug": slug, "kind": body.kind, "downloading": started}


@router.get("")
def projects(
    request: Request, actor: MaybeAdmin, kind: Literal["seeding", "ranking"] | None = None
):
    query = select(SeedingProject).order_by(SeedingProject.event_date.desc())
    if kind is not None:
        query = query.where(SeedingProject.kind == kind)
    if actor is None:
        query = query.where(SeedingProject.published.is_(True))
    with session_for(request) as session:
        return [
            dict(
                slug=p.slug,
                name=p.name,
                kind=p.kind,
                country_code=p.country_code,
                startgg_event_slug=p.startgg_event_slug,
                event_date=p.event_date,
                window_start=p.window_start,
                published=p.published,
            )
            for p in session.scalars(query)
        ]


@router.get("/{slug}")
def project_view(request: Request, slug: str, actor: MaybeAdmin):
    def operation(session):
        project = service.project_by_slug(session, slug)
        if actor is not None:
            return service.view(session, project)
        if not project.published:
            raise service.ProjectNotFound  # Drafts do not exist for readers.
        return service.public_view(session, project)

    return run(request, operation)


@router.get("/{slug}/monthly")
def monthly(
    request: Request,
    slug: str,
    actor: MaybeAdmin,
    month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
):
    """A ranking at the end of a month and how each player moved since the month before."""

    def operation(session):
        project = service.project_by_slug(session, slug)
        if actor is None and not project.published:
            raise service.ProjectNotFound
        return service.monthly(session, project, month)

    return run(request, operation)


@router.get("/{slug}/export.csv")
def export(request: Request, slug: str, actor: Admin):
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
    if body.reset_overrides:

        def reset(session):
            service.clear_all_overrides(session, service.project_by_slug(session, slug), actor)

        run(request, reset, write=True)
    if body.refresh:
        try:
            service.start_refresh(
                request.app.state.engine,
                slug,
                actor,
                request.app.state.settings.startgg_api_token,
                body.window_start,
                window_end=body.window_end,
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


@router.put("/{slug}/merges")
def merge(request: Request, slug: str, body: MergeRequest, actor: Admin):
    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        service.set_merge(session, project, body.from_player_id, body.to_player_id, actor)
        return {"status": "merged"}

    return run(request, operation, write=True)


@router.delete("/{slug}/merges/{player_id}")
def unmerge(request: Request, slug: str, player_id: str, actor: Admin):
    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        service.clear_merge(session, project, player_id, actor)
        return {"status": "unmerged"}

    return run(request, operation, write=True)


@router.put("/{slug}/duplicates")
def duplicate(request: Request, slug: str, body: DuplicateRequest, actor: Admin):
    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        service.set_duplicate(session, project, body.player_id, body.keep_player_id, actor)
        return {"status": "saved"}

    return run(request, operation, write=True)


@router.delete("/{slug}/duplicates/{player_id}")
def unduplicate(request: Request, slug: str, player_id: str, actor: Admin):
    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        service.clear_duplicate(session, project, player_id, actor)
        return {"status": "removed"}

    return run(request, operation, write=True)


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published: bool


@router.put("/{slug}/publish")
def publish(request: Request, slug: str, body: PublishRequest, actor: Admin):
    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        service.set_published(session, project, body.published, actor)
        return {"published": project.published}

    return run(request, operation, write=True)


# ---------------------------------------------------------------- pools (Mission 29)


class SwapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: str = Field(pattern=r"^\d{1,20}$")
    b: str = Field(pattern=r"^\d{1,20}$")


def _pool_seeding(session, slug):
    project = service.project_by_slug(session, slug)
    if project.kind != "seeding" or not project.startgg_event_slug:
        raise service.InvalidRequest("Solo los seedings de un evento de start.gg tienen pools.")
    _, rows = service.final_seeding(session, project)
    if not rows:
        raise service.InvalidRequest("Todavía no hay un cálculo de este seeding.")
    return project, rows


def _start_gg_pools(request, project, fresh=False):
    try:
        found = pools.read(
            request.app.state.settings.startgg_api_token, project.startgg_event_slug, fresh
        )
    except ImportFailure:
        raise HTTPException(502, "start.gg no respondió") from None
    if not found or not found["seeds"]:
        raise HTTPException(422, "start.gg todavía no armó las fases de este evento.")
    return found


@router.get("/{slug}/pools")
def pool_view(request: Request, slug: str, actor: Admin, fresh: bool = False):
    """The seeding laid on start.gg's pools, with each pool's strength and first-round
    warnings. Reads start.gg; writes nothing there."""
    from app.insights import engine
    from app.insights.preview import hub_players
    from app.teams import service as teams

    with session_for(request) as session:
        try:
            project, rows = _pool_seeding(session, slug)
        except service.ProjectNotFound:
            raise HTTPException(404, "Seeding no encontrado") from None
        except service.InvalidRequest as exc:
            raise HTTPException(422, str(exc)) from None
        found = _start_gg_pools(request, project, fresh)
        service._public_prefixes(session, rows, rows)
        hub = hub_players(session, [r["player_id"] for r in rows])
        shown = teams.display(session, set(hub.values()))
        data = engine.cached(session)
        return pools.build(
            rows,
            found,
            hub=hub,
            teams={p: v["team"] for p, v in shown.items() if v.get("team")},
            ranked=data.ranked,
            matches=data.matches,
        )


@router.post("/{slug}/pools/swap")
def pool_swap(request: Request, slug: str, body: SwapRequest, actor: Admin):
    """Two players trade seeds, and so places in the pools (two manual moves)."""

    def operation(session):
        project = service.project_by_slug(session, slug, lock=True)
        _, rows = service.final_seeding(session, project)
        by = {r["player_id"]: r for r in rows}
        if body.a == body.b or body.a not in by or body.b not in by:
            raise service.InvalidRequest("Elegí dos jugadores distintos del seeding.")
        a, b = by[body.a], by[body.b]
        service.set_override(
            session,
            project,
            body.a,
            b["seed"],
            f"Pools: cambia de lugar con {b['gamer_tag']}",
            actor,
        )
        service.set_override(
            session,
            project,
            body.b,
            a["seed"],
            f"Pools: cambia de lugar con {a['gamer_tag']}",
            actor,
        )
        return {"status": "swapped", "seeds": {body.a: b["seed"], body.b: a["seed"]}}

    return run(request, operation, write=True)


@router.post("/{slug}/pools/adopt")
def pool_adopt(request: Request, slug: str, actor: Admin):
    """Copy the seeding already loaded on start.gg into the hub, replacing manual moves."""
    with session_for(request) as session:
        try:
            project, rows = _pool_seeding(session, slug)
        except service.ProjectNotFound:
            raise HTTPException(404, "Seeding no encontrado") from None
        except service.InvalidRequest as exc:
            raise HTTPException(422, str(exc)) from None
        found = _start_gg_pools(request, project, fresh=True)
        project = service.project_by_slug(session, slug, lock=True)
        result = pools.adopt(session, project, rows, found, actor, service.audit)
        session.commit()
        return {"status": "adopted", **result}


# ---------------------------------------------------------------- upload to start.gg (Mission 30)


class PushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern=r"^[0-9a-f]{16}$")
    confirm: str = Field(max_length=200)


def _push_plan(request, slug):
    """(project slug, phase, plan) from the hub's seeding and start.gg read right now."""
    with session_for(request) as session:
        try:
            project, rows = _pool_seeding(session, slug)
        except service.ProjectNotFound:
            raise HTTPException(404, "Seeding no encontrado") from None
        except service.InvalidRequest as exc:
            raise HTTPException(422, str(exc)) from None
        event_slug = project.startgg_event_slug
    token = request.app.state.settings.startgg_api_token

    async def run_read():
        async with StartGGClient(token) as client:
            return await push.read(client, event_slug)

    try:
        phase, seeds = asyncio.run(run_read())
    except push.Blocked as exc:
        raise HTTPException(422, str(exc)) from None
    except ImportFailure:
        raise HTTPException(502, "start.gg no respondió") from None
    return phase, seeds, push.plan(rows, seeds)


@router.get("/{slug}/startgg")
def push_preview(request: Request, slug: str, actor: Admin):
    """What uploading would change on start.gg. Reads only."""
    phase, _, found = _push_plan(request, slug)
    return dict(
        enabled=request.app.state.settings.startgg_seeding_writes,
        phase=phase,
        confirm_text=slug,
        **{k: v for k, v in found.items() if k != "mapping"},
    )


@router.post("/{slug}/startgg")
def push_upload(request: Request, slug: str, body: PushRequest, actor: Admin):
    """Write the hub's seeding to start.gg's first phase, then read it back to verify."""
    phase, _, found = _push_plan(request, slug)
    try:
        push.check(
            found,
            enabled=request.app.state.settings.startgg_seeding_writes,
            typed=body.confirm,
            expected_text=slug,
            digest=body.digest,
        )
    except push.Blocked as exc:
        raise HTTPException(409, str(exc)) from None
    token = request.app.state.settings.startgg_api_token
    with session_for(request) as session:
        project = service.project_by_slug(session, slug)
        event_slug = project.startgg_event_slug

    async def run_write():
        async with StartGGClient(token) as client:
            await push.write(client, phase, found["mapping"])
            return (await push.read(client, event_slug))[1]

    try:
        after = asyncio.run(run_write())
    except ImportFailure:
        raise HTTPException(
            502,
            "start.gg rechazó el cambio o no respondió. Revisá que el token sea admin del torneo "
            "y que la fase no haya empezado.",
        ) from None
    wrong = push.verify(found["mapping"], after)
    with session_for(request) as session:
        project = service.project_by_slug(session, slug)
        service.audit(
            session,
            project,
            "push_startgg",
            actor,
            phase_id=phase["id"],
            changed=len(found["changes"]),
            verified=not wrong,
        )
        session.commit()
    pools._cache.pop(event_slug, None)
    return dict(
        status="pushed", phase=phase, changed=len(found["changes"]), verified=not wrong, wrong=wrong
    )
