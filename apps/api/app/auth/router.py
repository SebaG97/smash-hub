"""Smash Hub accounts over HTTP: sign-up, sign-in, profile and recovery (ADR-021)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.models import User
from app.auth.service import AuthError, MaybeUser, Member, SignedUser
from app.links import service as links

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
log = logging.getLogger(__name__)


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Registration(Body):
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)
    display_name: str | None = Field(default=None, max_length=60)


class Credentials(Body):
    login: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class Profile(Body):
    display_name: str = Field(min_length=1, max_length=60)


class PasswordChange(Body):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class Reset(Body):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=200)


def _session(request):
    return Session(request.app.state.engine, expire_on_commit=False)


def _fail(exc: AuthError):
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    raise HTTPException(exc.status, str(exc), headers=headers) from None


def _set_cookie(response, request, token, user):
    response.set_cookie(
        service.SESSION_COOKIE,
        token,
        max_age=service.session_days(user) * 86400,
        httponly=True,
        secure=request.app.state.settings.environment == "production",
        samesite="lax",
        path="/",
    )


def account(s, user: User | None, *, own=True):
    """What the web knows about the signed-in account."""
    if user is None:
        return None
    return dict(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        name=user.display_name,
        role=user.role,
        email=user.email if own else None,
        player=links.active_player(s, user.id),
    )


def _me(request, s, user):
    settings = request.app.state.settings
    return dict(
        user=account(s, user),
        # The organizers' shared key still works (transition, ADR-021).
        legacy_admin_key=settings.legacy_admin_active(),
    )


@router.get("/me")
def me(request: Request, user: MaybeUser):
    """Who is signed in (null when nobody) and which account features are available."""
    with _session(request) as s:
        return _me(request, s, user)


@router.post("/register", status_code=201)
def register(
    request: Request,
    body: Registration,
    x_requested_with: Annotated[str | None, Header()] = None,
):
    service.require_web_header(x_requested_with)
    client = service.client_of(request)
    if service.REGISTRATIONS.blocked(client):
        raise HTTPException(429, "Demasiados registros desde esta conexión. Probá más tarde.")
    # Every attempt counts, so the sign-up cannot be used to probe usernames and e-mails.
    service.REGISTRATIONS.hit(client)
    with _session(request) as s:
        try:
            with s.begin():
                user = service.register(
                    s,
                    username=body.username,
                    email=body.email,
                    password=body.password,
                    display_name=body.display_name,
                )
                user.last_login_at = service.now()
                token = service.open_session(s, user)
        except AuthError as exc:
            _fail(exc)
        response = JSONResponse(_me(request, s, user), status_code=201)
    _set_cookie(response, request, token, user)
    return response


@router.post("/login")
def login(
    request: Request,
    body: Credentials,
    x_requested_with: Annotated[str | None, Header()] = None,
    sh_session: Annotated[str | None, Cookie()] = None,
):
    service.require_web_header(x_requested_with)
    client = service.client_of(request)
    with _session(request) as s:
        failure = None
        with s.begin():
            try:
                user = service.authenticate(s, body.login, body.password, client)
            except AuthError as exc:
                failure = exc  # the audit of a failed attempt is committed on purpose
            else:
                # A new token on every sign-in (no session fixation).
                service.revoke(s, sh_session)
                token = service.open_session(s, user)
                service.audit(s, "login", user, target=user, ip=client)
        if failure is not None:
            _fail(failure)
        response = JSONResponse(_me(request, s, user))
    _set_cookie(response, request, token, user)
    return response


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    sh_session: Annotated[str | None, Cookie()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
):
    service.require_web_header(x_requested_with)
    with _session(request) as s, s.begin():
        service.revoke(s, sh_session)
    response = Response(status_code=204)
    response.delete_cookie(service.SESSION_COOKIE, path="/")
    return response


@router.put("/me")
def update_profile(request: Request, body: Profile, user: SignedUser):
    with _session(request) as s:
        with s.begin():
            row = s.get(User, user.id)
            row.display_name = service.clean_display_name(body.display_name, row.username)
        return _me(request, s, row)


@router.put("/password")
def change_password(
    request: Request,
    body: PasswordChange,
    user: SignedUser,
    sh_session: Annotated[str | None, Cookie()] = None,
):
    """New password; every other session of the account is closed."""
    with _session(request) as s:
        try:
            with s.begin():
                row = s.get(User, user.id, with_for_update=True)
                if not service.passwords.verify(row.password_hash, body.current_password):
                    raise AuthError("La contraseña actual no es correcta.", 403)
                service.set_password(s, row, body.new_password)
                closed = service.revoke_all(s, row.id, keep=sh_session)
                service.audit(s, "password_change", row, target=row, closed_sessions=closed)
        except AuthError as exc:
            _fail(exc)
        return dict(closed_sessions=closed)


@router.get("/sessions")
def sessions(request: Request, user: Member):
    with _session(request) as s:
        return dict(open=service.open_sessions(s, user.id))


@router.post("/sessions/revoke-others")
def revoke_others(
    request: Request, user: SignedUser, sh_session: Annotated[str | None, Cookie()] = None
):
    with _session(request) as s, s.begin():
        closed = service.revoke_all(s, user.id, keep=sh_session)
        service.audit(s, "sessions_revoked", user, target=user, closed_sessions=closed)
    return dict(closed_sessions=closed)


@router.post("/password/reset", status_code=204)
def reset(
    request: Request,
    body: Reset,
    x_requested_with: Annotated[str | None, Header()] = None,
):
    service.require_web_header(x_requested_with)
    client = service.client_of(request)
    wait = service.RESET_FAILURES.wait(client)
    if wait > 0:
        _fail(service._throttled(wait))
    with _session(request) as s:
        try:
            with s.begin():
                service.consume_reset(s, body.token, body.password)
        except AuthError as exc:
            if exc.status == 400:  # unknown or used token: slow down guessing
                service.RESET_FAILURES.fail(client)
            _fail(exc)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(service.SESSION_COOKIE, path="/")
    return response
