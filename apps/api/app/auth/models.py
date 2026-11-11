"""Smash Hub accounts, sessions and roles (Mission SH-AUTH-01, ADR-021).

An account exists on its own: it plays the Prode, and it may later be linked to a
competitive player record (app/links). Passwords are stored as Argon2id hashes and every
token (session, password reset) only as its SHA-256.
"""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Uuid,
)

from app.database.base import Base, Record

ROLES = ("user", "admin", "superadmin")


class User(Record, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin', 'superadmin')", name="role"),
        CheckConstraint("username ~ '^[a-z0-9_.-]{3,30}$'", name="username_format"),
    )
    # Lowercase, unique: what people type to sign in and what audits record.
    username = Column(String(30), nullable=False, unique=True)
    # Lowercase, unique. Null only for accounts created by the retired start.gg sign-in.
    email = Column(String(254), unique=True)
    # Argon2id. Null means the account cannot sign in with a password (legacy accounts).
    password_hash = Column(String(255))
    display_name = Column(String(120), nullable=False)
    role = Column(String(20), nullable=False, server_default="user")
    disabled_at = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True))
    last_login_at = Column(DateTime(timezone=True))


class UserSession(Record, Base):
    """A sign-in. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "user_sessions"
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))


class PasswordResetToken(Record, Base):
    """One-time password reset. Only the SHA-256 of the token is stored."""

    __tablename__ = "password_reset_tokens"
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))
    # The superadmin who issued the link (null only if that account was deleted).
    issued_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))


class AuthAuditEntry(Record, Base):
    """Append-only log of sign-ins, role changes, links and admin requests."""

    __tablename__ = "auth_audit_entries"
    action = Column(String(40), nullable=False, index=True)
    actor_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # Username at the time (or "clave:<name>" for the legacy key, "cli", "sistema").
    actor = Column(String(80), nullable=False)
    target_user_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    details = Column(JSON, nullable=False)
