"""Accounts, cookie sessions, roles and password resets (Mission SH-AUTH-01, ADR-021).

The session cookie carries a random token; the database keeps only its SHA-256, so a
leaked table opens no session. Every write that relies on the cookie must carry
`X-Requested-With: smashhub` (CSRF): a cross-site form cannot send it and CORS only lets
the hub's own origins add it. Roles are always read from the database on each request.
"""

import hashlib
import ipaddress
import math
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth import passwords
from app.auth.models import AuthAuditEntry, PasswordResetToken, User, UserSession

SESSION_COOKIE = "sh_session"
SESSION_DAYS = 30
# Accounts with an administrative role sign in again more often.
STAFF_SESSION_DAYS = 7
CSRF_HEADER_VALUE = "smashhub"
# One-time password-reset links issued by a superadmin (no e-mail yet).
MANUAL_RESET_HOURS = 24
STAFF = ("admin", "superadmin")
USERNAME = re.compile(r"^[a-z0-9_.-]{3,30}$")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
RESERVED = {
    "admin",
    "administrador",
    "administrator",
    "root",
    "sistema",
    "system",
    "superadmin",
    "smashhub",
    "soporte",
    "support",
    "cli",
    "moderador",
}


class AuthError(Exception):
    """A request the account system cannot take; the message is shown to the reader."""

    def __init__(self, message, status=400, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def now():
    return datetime.now(UTC)


# Per-process limits. The API runs as a single instance (infra/digitalocean/app.yaml),
# so these cover all its traffic; a restart forgets them (nothing is ever locked for good).


class Limiter:
    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)

    def blocked(self, key):
        recent, moment = self.hits[key], time.monotonic()
        while recent and moment - recent[0] > self.window:
            recent.popleft()
        return len(recent) >= self.limit

    def hit(self, key):
        self.hits[key].append(time.monotonic())

    def clear(self):
        self.hits.clear()


class Backoff:
    """Progressive waits after repeated failures: `free` failures cost nothing, then each
    one doubles the wait (1 s, 2 s, 4 s...) up to `cap` seconds. Attempts refused while
    waiting are not evaluated and do not count, so hammering does not lengthen the wait.
    A key is forgotten `idle` seconds after its last failure, or on `reset`."""

    MAX_KEYS = 50_000

    def __init__(self, free, cap, idle, clock=time.monotonic):
        self.free, self.cap, self.idle, self.clock = free, cap, idle, clock
        self.state: dict = {}

    def _delay(self, failures):
        return 0 if failures < self.free else min(self.cap, 2 ** (failures - self.free))

    def wait(self, key):
        """Seconds left before `key` may try again (0: now)."""
        found = self.state.get(key)
        if found is None:
            return 0
        failures, last = found
        elapsed = self.clock() - last
        if elapsed > self.idle:
            del self.state[key]
            return 0
        return max(0.0, self._delay(failures) - elapsed)

    def fail(self, key):
        failures, _ = self.state.get(key, (0, 0))
        if len(self.state) >= self.MAX_KEYS and key not in self.state:
            self._prune()
        self.state[key] = (failures + 1, self.clock())

    def reset(self, key):
        self.state.pop(key, None)

    def _prune(self):
        moment = self.clock()
        for key in [k for k, (_, last) in self.state.items() if moment - last > self.idle]:
            del self.state[key]
        while len(self.state) >= self.MAX_KEYS:  # still full: drop the oldest
            del self.state[min(self.state, key=lambda k: self.state[k][1])]

    def clear(self):
        self.state.clear()


# Sign-in throttling (ADR-021). Nothing here locks an account:
# - per address and account: 5 free failures, then up to 15 minutes. Only whoever keeps
#   failing from that address waits; the owner elsewhere is not affected;
# - per account from any address (guessing from many addresses): 20 free failures, then
#   at most 60 seconds. That bounded wait is all a third party can impose on someone else;
# - per address across accounts (spraying): 30 free failures, then up to 15 minutes.
# The per-account key is the typed login whether or not the account exists, so the
# answers reveal nothing about which accounts exist.
LOGIN_PAIR = Backoff(free=5, cap=900, idle=3600)
LOGIN_ACCOUNT = Backoff(free=20, cap=60, idle=900)
LOGIN_ADDRESS = Backoff(free=30, cap=900, idle=3600)
REGISTRATIONS = Limiter(20, 3600)
RESET_FAILURES = Backoff(free=10, cap=900, idle=3600)
THROTTLES = (LOGIN_PAIR, LOGIN_ACCOUNT, LOGIN_ADDRESS, REGISTRATIONS, RESET_FAILURES)


def client_of(request: Request):
    """The client's address. Behind App Platform the socket peer is DigitalOcean's ingress,
    which puts the visitor's address in `do-connecting-ip` (CLIENT_IP_HEADER). Only that
    configured header is read, only its last value (the one the proxy adds), and only if
    it is a valid IP; anything else falls back to the socket peer. Without the setting
    (local, tests) no header is trusted."""
    header = request.app.state.settings.client_ip_header
    if header:
        raw = request.headers.get(header)
        if raw:
            try:
                return str(ipaddress.ip_address(raw.split(",")[-1].strip()))
            except ValueError:
                pass
    return request.client.host if request.client else "?"


def _throttled(seconds):
    wait = max(1, math.ceil(seconds))
    return AuthError(
        f"Demasiados intentos fallidos. Esperá {wait} segundos y probá de nuevo.",
        429,
        retry_after=wait,
    )


# Identity.


def normalize_username(value):
    return (value or "").strip().lower()


def normalize_email(value):
    return (value or "").strip().lower()


def check_username(username):
    if not USERNAME.match(username):
        raise AuthError(
            "El usuario tiene de 3 a 30 caracteres: letras, números, punto, guion o guion bajo.",
            422,
        )
    if username in RESERVED:
        raise AuthError("Ese nombre de usuario está reservado.", 422)


def check_email(email):
    if len(email) > 254 or not EMAIL.match(email):
        raise AuthError("Ese correo no parece válido.", 422)


def clean_display_name(value, fallback):
    name = re.sub(r"\s+", " ", value or "").strip()[:40]
    return name or fallback


def register(s, *, username, email, password, display_name=None):
    """A new account. The public sign-up always creates role 'user'."""
    username, email = normalize_username(username), normalize_email(email)
    check_username(username)
    check_email(email)
    reason = passwords.problem(password, username=username, email=email)
    if reason:
        raise AuthError(reason, 422)
    if s.scalar(select(User.id).where(User.username == username)):
        raise AuthError("Ese nombre de usuario ya está en uso.", 409)
    if s.scalar(select(User.id).where(User.email == email)):
        raise AuthError("Ya hay una cuenta con ese correo. Probá recuperar la contraseña.", 409)
    user = User(
        username=username,
        email=email,
        password_hash=passwords.hash_password(password),
        display_name=clean_display_name(display_name, username),
        role="user",
        password_changed_at=now(),
    )
    s.add(user)
    s.flush()
    audit(s, "register", user, target=user)
    return user


def find_by_login(s, login):
    login = (login or "").strip().lower()
    column = User.email if "@" in login else User.username
    return s.scalar(select(User).where(column == login)) if login else None


def authenticate(s, login, password, address="?"):
    """The account behind a username or e-mail and its password, with progressive waits
    after failures (see the throttles above). Every failure looks the same from outside."""
    account = (login or "").strip().lower()[:254]
    pair = (address, account)
    wait = max(LOGIN_PAIR.wait(pair), LOGIN_ACCOUNT.wait(account), LOGIN_ADDRESS.wait(address))
    if wait > 0:
        raise _throttled(wait)  # not evaluated, so it does not count as a failure
    user = find_by_login(s, account)
    if user is None or not passwords.verify(user.password_hash, password):
        for throttle, key in (
            (LOGIN_PAIR, pair),
            (LOGIN_ACCOUNT, account),
            (LOGIN_ADDRESS, address),
        ):
            throttle.fail(key)
        if user is not None:
            audit(s, "login_failed", None, actor_name="sistema", target=user, ip=address)
        raise AuthError("Usuario o contraseña incorrectos.", 401)
    LOGIN_PAIR.reset(pair)
    LOGIN_ACCOUNT.reset(account)
    if user.disabled_at is not None:
        raise AuthError("Esta cuenta está desactivada. Hablá con un administrador.", 403)
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)
    user.last_login_at = now()
    return user


def set_password(s, user, password):
    reason = passwords.problem(password, username=user.username, email=user.email or "")
    if reason:
        raise AuthError(reason, 422)
    user.password_hash = passwords.hash_password(password)
    user.password_changed_at = now()


# Sessions.


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def session_days(user):
    return STAFF_SESSION_DAYS if user.role in STAFF else SESSION_DAYS


def open_session(s, user):
    token = secrets.token_urlsafe(32)
    s.add(
        UserSession(
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=now() + timedelta(days=session_days(user)),
        )
    )
    return token


def user_for(s, token):
    if not token or len(token) > 200:
        return None
    return s.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == _hash(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > func.now(),
            User.disabled_at.is_(None),
        )
    )


def revoke(s, token):
    if token:
        s.execute(
            update(UserSession)
            .where(UserSession.token_hash == _hash(token), UserSession.revoked_at.is_(None))
            .values(revoked_at=now())
        )


def revoke_all(s, user_id, *, keep=None):
    """Close every open session of an account (except `keep`, the caller's own)."""
    query = update(UserSession).where(
        UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
    )
    if keep:
        query = query.where(UserSession.token_hash != _hash(keep))
    return s.execute(query.values(revoked_at=now())).rowcount


def open_sessions(s, user_id):
    return s.scalar(
        select(func.count())
        .select_from(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > func.now(),
        )
    )


# Password resets.


def void_resets(s, *, user_id=None, issued_by=None):
    """Unused reset links stop working: those of an account, or those a person issued."""
    query = update(PasswordResetToken).where(PasswordResetToken.used_at.is_(None))
    if user_id is not None:
        query = query.where(PasswordResetToken.user_id == user_id)
    if issued_by is not None:
        query = query.where(PasswordResetToken.issued_by == issued_by)
    return s.execute(query.values(used_at=now())).rowcount


def issue_reset(s, user, *, issued_by):
    """A one-time link a superadmin hands over through a trusted channel. 256 random bits;
    only the SHA-256 is stored. Earlier unused links of the account stop working."""
    void_resets(s, user_id=user.id)
    token = secrets.token_urlsafe(32)
    expires = now() + timedelta(hours=MANUAL_RESET_HOURS)
    s.add(
        PasswordResetToken(
            user_id=user.id, token_hash=_hash(token), expires_at=expires, issued_by=issued_by.id
        )
    )
    return token, expires


def consume_reset(s, token, password):
    """Set a new password with a reset token. Closes every session of the account."""
    row = (
        s.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == _hash(token))
            .with_for_update()
        )
        if token and len(token) <= 200
        else None
    )
    expired = AuthError(
        "El enlace de recuperación venció o ya se usó. Pedile uno nuevo a un administrador.", 400
    )
    if row is None or row.used_at is not None or row.expires_at <= now():
        raise expired
    user = s.get(User, row.user_id)
    issuer = s.get(User, row.issued_by) if row.issued_by else None
    # The account must be active, and whoever issued the link must still be a superadmin.
    if user is None or user.disabled_at is not None:
        raise expired
    if issuer is None or issuer.role != "superadmin" or issuer.disabled_at is not None:
        raise expired
    set_password(s, user, password)
    row.used_at = now()
    revoke_all(s, user.id)
    audit(s, "password_reset", user, target=user, issued_by=issuer.username)
    return user


def reset_url(settings, token):
    # In the fragment, not the query: it never reaches a server log or a Referer.
    return f"{settings.web_origin()}/recuperar/nueva#token={token}"


# Audit.


def audit(s, action, actor, *, actor_name=None, target=None, **details):
    s.add(
        AuthAuditEntry(
            action=action,
            actor_id=actor.id if actor is not None else None,
            actor=(actor_name or (actor.username if actor is not None else "sistema"))[:80],
            target_user_id=target.id if target is not None else None,
            details=details,
        )
    )


# FastAPI dependencies.


def require_web_header(x_requested_with):
    if x_requested_with != CSRF_HEADER_VALUE:
        raise HTTPException(403, "Falta el encabezado de la web del hub.")


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
    require_web_header(x_requested_with)
    user = _reader(request, sh_session)
    if user is None:
        raise HTTPException(401, "Ingresá a tu cuenta para continuar.")
    return user


def _role(*allowed):
    def check(
        request: Request,
        sh_session: Annotated[str | None, Cookie()] = None,
        x_requested_with: Annotated[str | None, Header()] = None,
    ):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            require_web_header(x_requested_with)
        user = _reader(request, sh_session)
        if user is None:
            raise HTTPException(401, "Ingresá con una cuenta autorizada.")
        if user.role not in allowed:
            raise HTTPException(403, "Tu cuenta no tiene permiso para esto.")
        return user

    return check


MaybeUser = Annotated[User | None, Depends(_reader)]
# Signed in, for writes (always checks the web header).
SignedUser = Annotated[User, Depends(_writer)]
# Signed in with any role; the web header is checked on writes only.
Member = Annotated[User, Depends(_role("user", *STAFF))]
Staff = Annotated[User, Depends(_role(*STAFF))]
Superadmin = Annotated[User, Depends(_role("superadmin"))]
