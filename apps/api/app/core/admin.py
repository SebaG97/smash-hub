"""Shared admin key for HTTP writes (ADR-011): seeding, rankings and imports."""

import hmac
import re
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

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
