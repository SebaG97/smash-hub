from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database.base import Base, Record


class Player(Record, Base):
    __tablename__ = "players"
    manual_locked = Column(Boolean, nullable=False, server_default=text("false"))
    tag = Column(String(120), nullable=False, index=True)
    country_id = Column(Uuid, ForeignKey("countries.id"), index=True)
    region_id = Column(Uuid, index=True)
    # {character name: costume 1-8} chosen by organizers for share images.
    costumes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    __table_args__ = (
        ForeignKeyConstraint(["region_id", "country_id"], ["regions.id", "regions.country_id"]),
        CheckConstraint("region_id IS NULL OR country_id IS NOT NULL", name="region_country"),
    )


class PlayerAlias(Record, Base):
    __tablename__ = "player_aliases"
    player_id = Column(Uuid, ForeignKey("players.id"), nullable=False, index=True)
    tag = Column(String(120), nullable=False, index=True)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="alias_dates"),
    )


class ExternalIdentity(Record, Base):
    __tablename__ = "external_identities"
    player_id = Column(Uuid, ForeignKey("players.id"), nullable=False, index=True)
    data_source_id = Column(Uuid, ForeignKey("data_sources.id"), nullable=False, index=True)
    external_id = Column(String(200), nullable=False)
    synced_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("data_source_id", "external_id"),)
