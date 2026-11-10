"""People who sign in to play the Prode (Mission SH-PRODE-01, ADR-020).

The hub's first personal data: only what start.gg's public profile already shows.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, Uuid

from app.database.base import Base, Record


class User(Record, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)
    provider = Column(String(20), nullable=False)
    provider_user_id = Column(String(40), nullable=False)
    display_name = Column(String(120), nullable=False)
    slug = Column(String(120))
    # The start.gg player behind the account, so Prode achievements reach their profile.
    startgg_player_id = Column(String(20), index=True)
    banned_at = Column(DateTime(timezone=True))


class UserSession(Record, Base):
    """A sign-in. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "user_sessions"
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
