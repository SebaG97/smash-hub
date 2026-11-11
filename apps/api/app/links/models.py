"""Links between Smash Hub accounts and competitive player records (ADR-021).

A link is history: unlinking stamps `unlinked_at` and keeps the row. Partial unique
indexes allow one active link per account and one per player, so a conflicting link can
only happen through the explicit, audited replace of an administrator.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)

from app.database.base import Base, Record

LINK_METHODS = ("request", "admin", "startgg_legacy")
REQUEST_STATUSES = ("pending", "approved", "rejected", "cancelled")


class PlayerLink(Record, Base):
    __tablename__ = "player_links"
    __table_args__ = (
        CheckConstraint("method IN ('request', 'admin', 'startgg_legacy')", name="method"),
        Index(
            "uq_player_links_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("unlinked_at IS NULL"),
        ),
        Index(
            "uq_player_links_active_player",
            "player_id",
            unique=True,
            postgresql_where=text("unlinked_at IS NULL"),
        ),
    )
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id = Column(Uuid, ForeignKey("players.id"), nullable=False, index=True)
    method = Column(String(20), nullable=False)
    request_id = Column(Uuid, ForeignKey("player_link_requests.id", ondelete="SET NULL"))
    # How the administrator checked that the account belongs to the player.
    verification = Column(String(500), nullable=False)
    linked_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    linked_by_name = Column(String(80), nullable=False)
    unlinked_at = Column(DateTime(timezone=True))
    unlinked_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    unlinked_by_name = Column(String(80))
    unlink_reason = Column(String(500))


class PlayerLinkRequest(Record, Base):
    __tablename__ = "player_link_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')", name="status"
        ),
        Index(
            "uq_player_link_requests_pending_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id = Column(Uuid, ForeignKey("players.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, server_default="pending")
    # Shown to the person, who proves the account is theirs by putting it somewhere only
    # the player controls (start.gg bio, the community's Discord) or showing it in person.
    code = Column(String(16), nullable=False)
    evidence = Column(String(1000), nullable=False)
    reviewed_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by_name = Column(String(80))
    reviewed_at = Column(DateTime(timezone=True))
    review_note = Column(String(500))
