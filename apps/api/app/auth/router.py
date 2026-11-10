"""Sign-in with start.gg for the Prode (ADR-020)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.service import MaybeUser

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
log = logging.getLogger(__name__)


def _settings(request):
    settings = request.app.state.settings
    if not service.enabled(settings):
        raise HTTPException(503, "El ingreso con start.gg todavía no está configurado.")
    return settings


def _web(settings, path):
    """Back to the web: its origin is the first CORS origin (same site in production)."""
    return settings.cors_origins[0].rstrip("/") + path


def _secure(settings):
    return settings.environment == "production"


@router.get("/startgg/login", include_in_schema=False)
def login(request: Request, next: Annotated[str | None, Query(max_length=300)] = None):
    settings = _settings(request)
    state, cookie = service.new_state(settings, next)
    response = RedirectResponse(service.authorize_url(settings, state), status_code=303)
    response.set_cookie(
        service.STATE_COOKIE,
        cookie,
        max_age=service.STATE_MINUTES * 60,
        httponly=True,
        secure=_secure(settings),
        samesite="lax",
        path="/api/v1/auth",
    )
    return response


@router.get("/startgg/callback", include_in_schema=False)
def callback(
    request: Request,
    code: Annotated[str | None, Query(max_length=2000)] = None,
    state: Annotated[str | None, Query(max_length=200)] = None,
    sh_oauth: Annotated[str | None, Cookie()] = None,
):
    settings = _settings(request)
    next_path = service.check_state(settings, state, sh_oauth)
    if next_path is None or not code:
        return _failed(settings, "estado")
    try:
        identity = service.fetch_identity(settings, code)
    except service.SignInFailure as exc:
        log.warning("start.gg sign-in failed: %s", exc)
        return _failed(settings, "startgg")
    with Session(request.app.state.engine, expire_on_commit=False) as s, s.begin():
        user = service.upsert_user(s, identity)
        if user.banned_at is not None:
            return _failed(settings, "bloqueado")
        token = service.open_session(s, user)
    response = RedirectResponse(_web(settings, next_path), status_code=303)
    response.delete_cookie(service.STATE_COOKIE, path="/api/v1/auth")
    response.set_cookie(
        service.SESSION_COOKIE,
        token,
        max_age=service.SESSION_DAYS * 86400,
        httponly=True,
        secure=_secure(settings),
        samesite="lax",
        path="/",
    )
    return response


def _failed(settings, reason):
    response = RedirectResponse(_web(settings, f"/prode?ingreso={reason}"), status_code=303)
    response.delete_cookie(service.STATE_COOKIE, path="/api/v1/auth")
    return response


@router.get("/me")
def me(request: Request, user: MaybeUser):
    """Who is signed in (null when nobody) and whether signing in is available."""
    return dict(
        enabled=service.enabled(request.app.state.settings),
        user=None
        if user is None
        else dict(
            id=str(user.id),
            name=user.display_name,
            slug=user.slug,
            startgg_player_id=user.startgg_player_id,
        ),
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    sh_session: Annotated[str | None, Cookie()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
):
    if x_requested_with != service.CSRF_HEADER_VALUE:
        raise HTTPException(403, "Falta el encabezado de la web del hub.")
    with Session(request.app.state.engine) as s, s.begin():
        service.revoke(s, sh_session)
    response = Response(status_code=204)
    response.delete_cookie(service.SESSION_COOKIE, path="/")
    return response
