"""Who may use the organizers' routes: seeding, rankings, imports, teams, Prode (ADR-021).

An administrator's personal session (role admin or superadmin) is the way in. The old
shared key (ADR-011) still works during the transition, but only while ADMIN_TOKEN_EXPIRES
is set and in the future; every use is logged so the retirement can be checked. Both
return the actor name the existing audit logs record: the username for a session,
"clave:<name>" for the shared key.
"""

import hmac
import logging
import re
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import service

FAILURE_WINDOW, FAILURE_LIMIT = 600, 10
_failures: dict[str, deque] = defaultdict(deque)
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
log = logging.getLogger(__name__)


def _record(request, user, action, actor_name=None):
    with Session(request.app.state.engine) as s, s.begin():
        service.audit(
            s,
            action,
            user,
            actor_name=actor_name,
            method=request.method,
            path=request.url.path[:300],
        )


def _legacy(request, authorization, x_admin_name):
    settings = request.app.state.settings
    if not settings.legacy_admin_active():
        raise HTTPException(
            401, "La clave compartida de organizadores ya no se acepta: ingresá con tu cuenta."
        )
    client = service.client_of(request)
    now = time.monotonic()
    recent = _failures[client]
    while recent and now - recent[0] > FAILURE_WINDOW:
        recent.popleft()
    if len(recent) >= FAILURE_LIMIT:
        raise HTTPException(429, "Demasiados intentos fallidos; espera unos minutos.")
    given = (authorization or "").removeprefix("Bearer ").strip()
    secret = settings.admin_token.get_secret_value().encode()
    if not given or not hmac.compare_digest(given.encode(), secret):
        recent.append(now)
        raise HTTPException(401, "Clave de administración incorrecta.")
    name = re.sub(r"[^\w .@-]", "", x_admin_name or "", flags=re.UNICODE).strip()[:60]
    actor = f"clave:{name or 'admin'}"[:60]
    log.warning("Legacy admin key used (%s %s)", request.method, request.url.path[:100])
    _record(request, None, "legacy_admin_request", actor_name=actor)
    return actor


def _resolve(request, authorization, x_admin_name, x_requested_with, sh_session, *, required):
    signed_in = False
    if sh_session:
        user = service._reader(request, sh_session)
        signed_in = user is not None
        if user is not None and user.role in service.STAFF:
            if request.method not in SAFE_METHODS:
                service.require_web_header(x_requested_with)
                _record(request, user, "admin_request")
            return user.username
    if authorization:
        return _legacy(request, authorization, x_admin_name)
    if not required:
        return None
    if signed_in:
        raise HTTPException(403, "Tu cuenta no tiene permisos de administración.")
    raise HTTPException(401, "Ingresá con una cuenta de administrador.")


def admin(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_admin_name: Annotated[str | None, Header()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
    sh_session: Annotated[str | None, Cookie()] = None,
) -> str:
    """An administrator's session (or, during the transition, the shared key)."""
    return _resolve(
        request, authorization, x_admin_name, x_requested_with, sh_session, required=True
    )


Admin = Annotated[str, Depends(admin)]


def optional_admin(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_admin_name: Annotated[str | None, Header()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
    sh_session: Annotated[str | None, Cookie()] = None,
) -> str | None:
    """Reader pages: no administrator means a public reader; a wrong key is still rejected."""
    return _resolve(
        request, authorization, x_admin_name, x_requested_with, sh_session, required=False
    )


MaybeAdmin = Annotated[str | None, Depends(optional_admin)]
