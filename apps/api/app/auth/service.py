"""Sign-in with start.gg (OAuth authorization code) and cookie sessions (ADR-020).

start.gg's access token is used once, to read who signed in, and never stored. The
session cookie carries a random token; the database keeps only its SHA-256, so a leaked
table opens no session.
"""

import asyncio
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.models import User, UserSession

AUTHORIZE_URL = "https://start.gg/oauth/authorize"
TOKEN_URL = "https://api.start.gg/oauth/access_token"
GRAPHQL_URL = "https://api.start.gg/gql/alpha"
SCOPE = "user.identity"
SESSION_COOKIE = "sh_session"
STATE_COOKIE = "sh_oauth"
SESSION_DAYS = 30
STATE_MINUTES = 10
# Writes with the session cookie must carry this header: a cross-site form cannot send
# it, and CORS only lets the hub's own origins add it (CSRF).
CSRF_HEADER_VALUE = "smashhub"

CURRENT_USER = """
query { currentUser { id slug player { id gamerTag prefix } } }
"""


class SignInFailure(Exception):
    pass


def enabled(settings):
    return bool(
        settings.startgg_oauth_client_id
        and settings.startgg_oauth_client_secret
        and settings.startgg_oauth_redirect_uri
    )


def safe_next(value):
    """Only paths of this site: never another host after signing in."""
    if (
        not value
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or len(value) > 300
    ):
        return "/"
    return value


def _signature(settings, text):
    key = settings.startgg_oauth_client_secret.get_secret_value().encode()
    return hmac.new(key, text.encode(), hashlib.sha256).hexdigest()


def new_state(settings, next_path):
    """(state for start.gg, value of the short-lived cookie that proves it is ours)."""
    state = secrets.token_urlsafe(24)
    text = f"{state}|{safe_next(next_path)}"
    return state, f"{text}|{_signature(settings, text)}"


def check_state(settings, given, cookie):
    """The page to return to, or None when the state does not match the cookie."""
    try:
        state, next_path, signature = (cookie or "").rsplit("|", 2)
    except ValueError:
        return None
    text = f"{state}|{next_path}"
    if not given or not hmac.compare_digest(signature, _signature(settings, text)):
        return None
    if not hmac.compare_digest(state, given):
        return None
    return safe_next(next_path)


def authorize_url(settings, state):
    query = urlencode(
        dict(
            response_type="code",
            client_id=settings.startgg_oauth_client_id,
            scope=SCOPE,
            redirect_uri=settings.startgg_oauth_redirect_uri,
            state=state,
        )
    )
    return f"{AUTHORIZE_URL}?{query}"


async def _identity(settings, code, transport=None):
    async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), transport=transport) as http:
        token = await http.post(
            TOKEN_URL,
            json=dict(
                grant_type="authorization_code",
                client_secret=settings.startgg_oauth_client_secret.get_secret_value(),
                code=code,
                scope=SCOPE,
                client_id=settings.startgg_oauth_client_id,
                redirect_uri=settings.startgg_oauth_redirect_uri,
            ),
        )
        access = token.json().get("access_token") if token.status_code == 200 else None
        if not access:
            raise SignInFailure("startgg_token_rejected")
        answer = await http.post(
            GRAPHQL_URL,
            json={"query": CURRENT_USER},
            headers={"Authorization": f"Bearer {access}"},
        )
        user = ((answer.json() or {}).get("data") or {}).get("currentUser") or {}
        if answer.status_code != 200 or not user.get("id"):
            raise SignInFailure("startgg_user_unreadable")
        return user


def fetch_identity(settings, code):
    """start.gg's public profile of whoever signed in."""
    try:
        return asyncio.run(_identity(settings, code))
    except (httpx.HTTPError, ValueError) as exc:
        raise SignInFailure("startgg_unreachable") from exc


def upsert_user(session, identity):
    player = identity.get("player") or {}
    name = (player.get("gamerTag") or identity.get("slug") or "Jugador").strip()[:120]
    user = session.scalar(
        select(User).where(User.provider == "startgg", User.provider_user_id == str(identity["id"]))
    )
    if user is None:
        user = User(provider="startgg", provider_user_id=str(identity["id"]))
        session.add(user)
    user.display_name = name
    user.slug = (identity.get("slug") or None) and str(identity["slug"])[:120]
    user.startgg_player_id = str(player["id"]) if player.get("id") else None
    session.flush()
    return user


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def open_session(session, user):
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=datetime.now(UTC) + timedelta(days=SESSION_DAYS),
        )
    )
    return token


def user_for(session, token):
    if not token or len(token) > 200:
        return None
    return session.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == _hash(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
            User.banned_at.is_(None),
        )
    )


def revoke(session, token):
    if token:
        session.execute(
            update(UserSession)
            .where(UserSession.token_hash == _hash(token), UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )


def _reader(request: Request, sh_session: Annotated[str | None, Cookie()] = None):
    if not sh_session:
        return None
    with Session(request.app.state.engine, expire_on_commit=False) as s:
        return user_for(s, sh_session)


def _writer(
    request: Request,
    sh_session: Annotated[str | None, Cookie()] = None,
    x_requested_with: Annotated[str | None, Header()] = None,
):
    if x_requested_with != CSRF_HEADER_VALUE:
        raise HTTPException(403, "Falta el encabezado de la web del hub.")
    user = _reader(request, sh_session)
    if user is None:
        raise HTTPException(401, "Ingresá con start.gg para jugar el Prode.")
    return user


MaybeUser = Annotated[User | None, Depends(_reader)]
SignedUser = Annotated[User, Depends(_writer)]
