"""Helpers for tests that need accounts, sessions or the legacy admin key (ADR-021)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.auth import service

# The shared key only works while dated; tests keep it valid.
LEGACY_EXPIRES = datetime.now(UTC) + timedelta(days=30)
WEB = {"X-Requested-With": "smashhub"}
PASSWORD = "una frase bastante larga"


def make_user(engine, username, *, role="user", email=None, password=PASSWORD):
    """An account straight in the database (role included), for setting up tests."""
    with Session(engine, expire_on_commit=False) as s, s.begin():
        user = service.register(
            s, username=username, email=email or f"{username}@example.com", password=password
        )
        user.role = role
    return user


def sign_in(client, login, password=PASSWORD):
    r = client.post("/api/v1/auth/login", json=dict(login=login, password=password), headers=WEB)
    assert r.status_code == 200, r.text
    return client
