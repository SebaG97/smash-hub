"""Administration of accounts, roles and player links (ADR-021).

Administrators review link requests and link or unlink players. Only superadmins change
roles, disable accounts or issue manual password-reset links. Neither works with the
legacy shared key: these routes need a personal session.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.models import AuthAuditEntry, User
from app.auth.service import AuthError, Staff, Superadmin
from app.links import service as links

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoleChange(Body):
    role: Literal["user", "admin", "superadmin"]


class StatusChange(Body):
    disabled: bool
    reason: str = Field(default="", max_length=500)


class Verification(Body):
    verification: str = Field(min_length=1, max_length=500)


class Rejection(Body):
    note: str = Field(min_length=1, max_length=500)


class DirectLink(Body):
    user_id: UUID
    player_id: UUID
    verification: str = Field(min_length=1, max_length=500)
    replace: bool = False
    reason: str | None = Field(default=None, max_length=500)


class Unlink(Body):
    reason: str = Field(min_length=1, max_length=500)


def _session(request):
    return Session(request.app.state.engine, expire_on_commit=False)


def _fail(exc: AuthError):
    raise HTTPException(exc.status, str(exc)) from None


def _run(request, change):
    with _session(request) as s:
        try:
            with s.begin():
                result = change(s)
        except AuthError as exc:
            _fail(exc)
        return result


def _user_row(s, user, *, viewer):
    return dict(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        # E-mail is personal data: only superadmins see it.
        email=user.email if viewer.role == "superadmin" else None,
        disabled=user.disabled_at is not None,
        can_sign_in=user.password_hash is not None,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        player=links.active_player(s, user.id),
    )


# Accounts and roles.


@router.get("/users")
def users(
    request: Request,
    staff: Staff,
    q: Annotated[str, Query(max_length=60)] = "",
    role: Literal["user", "admin", "superadmin"] | None = None,
):
    with _session(request) as s:
        query = select(User).order_by(User.created_at.desc()).limit(50)
        text = " ".join(q.split()).lower()
        if text:
            pattern = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            matches = User.username.ilike(pattern, escape="\\") | User.display_name.ilike(
                pattern, escape="\\"
            )
            if staff.role == "superadmin":
                matches = matches | User.email.ilike(pattern, escape="\\")
            query = query.where(matches)
        if role:
            query = query.where(User.role == role)
        return [_user_row(s, u, viewer=staff) for u in s.scalars(query)]


def _active_superadmins(s):
    return s.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "superadmin", User.disabled_at.is_(None))
    )


def _target(s, user_id):
    user = s.get(User, user_id, with_for_update=True)
    if user is None:
        raise AuthError("No existe esa cuenta.", 404)
    return user


@router.put("/users/{user_id}/role")
def change_role(request: Request, user_id: UUID, body: RoleChange, actor: Superadmin):
    def change(s):
        user = _target(s, user_id)
        if user.id == actor.id:
            raise AuthError("No podés cambiar tu propio rol.", 403)
        if user.role == body.role:
            return _user_row(s, user, viewer=actor)
        if user.role == "superadmin" and _active_superadmins(s) <= 1:
            raise AuthError("Tiene que quedar al menos un superadministrador activo.", 409)
        if body.role != "user" and user.password_hash is None:
            raise AuthError("Esa cuenta no puede ingresar con contraseña.", 409)
        before, user.role = user.role, body.role
        # The person signs in again under the new role (and its session length).
        closed = service.revoke_all(s, user.id)
        if before == "superadmin":
            service.void_resets(s, issued_by=user.id)  # links they issued die with the role
        service.audit(
            s,
            "role_changed",
            actor,
            target=user,
            before=before,
            after=body.role,
            closed_sessions=closed,
        )
        return _user_row(s, user, viewer=actor)

    return _run(request, change)


@router.put("/users/{user_id}/status")
def change_status(request: Request, user_id: UUID, body: StatusChange, actor: Superadmin):
    def change(s):
        user = _target(s, user_id)
        if user.id == actor.id:
            raise AuthError("No podés desactivar tu propia cuenta.", 403)
        if body.disabled == (user.disabled_at is not None):
            return _user_row(s, user, viewer=actor)
        reason = " ".join(body.reason.split())
        if body.disabled:
            if len(reason) < 5:
                raise AuthError("Indicá el motivo de la desactivación.", 422)
            if user.role == "superadmin" and _active_superadmins(s) <= 1:
                raise AuthError("Tiene que quedar al menos un superadministrador activo.", 409)
            user.disabled_at = service.now()
            closed = service.revoke_all(s, user.id)
            service.void_resets(s, user_id=user.id)
            service.void_resets(s, issued_by=user.id)
            service.audit(
                s, "account_disabled", actor, target=user, reason=reason, closed_sessions=closed
            )
        else:
            user.disabled_at = None
            service.audit(s, "account_enabled", actor, target=user, reason=reason)
        return _user_row(s, user, viewer=actor)

    return _run(request, change)


@router.post("/users/{user_id}/sessions/revoke")
def revoke_sessions(request: Request, user_id: UUID, actor: Superadmin):
    def change(s):
        user = _target(s, user_id)
        closed = service.revoke_all(s, user.id)
        service.audit(s, "sessions_revoked", actor, target=user, closed_sessions=closed)
        return dict(closed_sessions=closed)

    return _run(request, change)


@router.post("/users/{user_id}/password-reset")
def manual_reset(request: Request, user_id: UUID, actor: Superadmin):
    """A one-time link (24 h) to hand to the person through a channel you trust. It is in
    this response only (never cached, logged or audited); only its hash is stored."""
    settings = request.app.state.settings

    def change(s):
        user = _target(s, user_id)
        if user.disabled_at is not None:
            raise AuthError("Esa cuenta está desactivada.", 409)
        if user.password_hash is None:
            raise AuthError("Esa cuenta no puede ingresar con contraseña.", 409)
        token, expires = service.issue_reset(s, user, issued_by=actor)
        service.audit(
            s, "password_reset_issued", actor, target=user, expires_at=expires.isoformat()
        )
        return dict(url=service.reset_url(settings, token), expires_at=expires.isoformat())

    return JSONResponse(
        _run(request, change), headers={"Cache-Control": "no-store", "Pragma": "no-cache"}
    )


@router.get("/status")
def status(request: Request, actor: Superadmin):
    """How far the move away from the shared key has gone."""
    settings = request.app.state.settings
    with _session(request) as s:
        counts = dict(
            s.execute(
                select(User.role, func.count())
                .where(User.disabled_at.is_(None))
                .group_by(User.role)
            ).all()
        )
        last_legacy = s.scalar(
            select(func.max(AuthAuditEntry.created_at)).where(
                AuthAuditEntry.action == "legacy_admin_request"
            )
        )
    expires = settings.admin_token_expires
    return dict(
        roles=dict(
            user=counts.get("user", 0),
            admin=counts.get("admin", 0),
            superadmin=counts.get("superadmin", 0),
        ),
        legacy_admin_key=dict(
            configured=settings.admin_token is not None,
            active=settings.legacy_admin_active(),
            expires_at=expires.isoformat() if expires else None,
            last_used_at=last_legacy.isoformat() if last_legacy else None,
        ),
    )


@router.get("/audit")
def audit_log(
    request: Request,
    actor: Superadmin,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    action: Annotated[str | None, Query(max_length=40)] = None,
):
    with _session(request) as s:
        query = select(AuthAuditEntry).order_by(AuthAuditEntry.created_at.desc()).limit(limit)
        if action:
            query = query.where(AuthAuditEntry.action == action)
        rows = list(s.scalars(query))
        names = {
            u.id: u.username
            for u in s.scalars(
                select(User).where(User.id.in_({r.target_user_id for r in rows} - {None}))
            )
        }
        return [
            dict(
                at=r.created_at.isoformat(),
                action=r.action,
                actor=r.actor,
                target=names.get(r.target_user_id),
                details=r.details,
            )
            for r in rows
        ]


# Player links.


@router.get("/link-requests")
def link_requests(
    request: Request,
    staff: Staff,
    status: Literal["pending", "approved", "rejected", "cancelled"] | None = "pending",
):
    with _session(request) as s:
        return links.describe_requests(s, links.requests_by_status(s, status), staff=True)


@router.post("/link-requests/{request_id}/approve")
def approve(request: Request, request_id: UUID, body: Verification, staff: Staff):
    def change(s):
        row = links.approve(s, staff, request_id, body.verification)
        return dict(link=str(row.id))

    return _run(request, change)


@router.post("/link-requests/{request_id}/reject")
def reject(request: Request, request_id: UUID, body: Rejection, staff: Staff):
    def change(s):
        links.reject(s, staff, request_id, body.note)
        return dict(status="rejected")

    return _run(request, change)


@router.get("/links")
def active_links(request: Request, staff: Staff, q: Annotated[str, Query(max_length=60)] = ""):
    with _session(request) as s:
        return links.active_links(s, q)


@router.get("/players")
def players(request: Request, staff: Staff, q: Annotated[str, Query(max_length=60)] = ""):
    with _session(request) as s:
        return links.search_players(s, q)


@router.post("/links", status_code=201)
def create_link(request: Request, body: DirectLink, staff: Staff):
    def change(s):
        row = links.link(
            s,
            staff,
            body.user_id,
            body.player_id,
            body.verification,
            replace=body.replace,
            reason=body.reason,
        )
        return dict(link=str(row.id))

    return _run(request, change)


@router.post("/links/{link_id}/unlink")
def unlink(request: Request, link_id: UUID, body: Unlink, staff: Staff):
    def change(s):
        links.unlink(s, staff, link_id, body.reason)
        return dict(status="unlinked")

    return _run(request, change)
