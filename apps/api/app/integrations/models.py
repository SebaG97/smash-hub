from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)

from app.database.base import Base, Record


class DataSource(Record, Base):
    __tablename__ = "data_sources"
    slug = Column(String(100), nullable=False, unique=True)
    name = Column(String(160), nullable=False)
    base_url = Column(Text, nullable=False)


class ImportJob(Record, Base):
    __tablename__ = "import_jobs"
    data_source_id = Column(Uuid, ForeignKey("data_sources.id"), nullable=False, index=True)
    idempotency_key = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, server_default="pending")
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    error_code = Column(String(80))
    __table_args__ = (
        UniqueConstraint("data_source_id", "idempotency_key"),
        CheckConstraint("status IN ('pending','running','completed','failed')", name="job_status"),
        CheckConstraint(
            "finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)",
            name="job_dates",
        ),
    )


class ExternalMapping(Record, Base):
    __tablename__ = "external_mappings"
    data_source_id = Column(Uuid, ForeignKey("data_sources.id"), nullable=False, index=True)
    entity_type = Column(String(30), nullable=False)
    external_id = Column(String(200), nullable=False)
    tournament_id = Column(Uuid, ForeignKey("tournaments.id"), index=True)
    event_id = Column(Uuid, ForeignKey("events.id"), index=True)
    set_id = Column(Uuid, ForeignKey("sets.id"), index=True)
    entrant_id = Column(Uuid, ForeignKey("event_entrants.id"), index=True)
    synced_at = Column(DateTime(timezone=True), nullable=False)
    source_updated_at = Column(DateTime(timezone=True))
    payload_hash = Column(String(64))
    __table_args__ = (
        UniqueConstraint("data_source_id", "entity_type", "external_id"),
        UniqueConstraint("data_source_id", "tournament_id"),
        UniqueConstraint("data_source_id", "event_id"),
        UniqueConstraint("data_source_id", "set_id"),
        UniqueConstraint("data_source_id", "entrant_id"),
        CheckConstraint(
            """(entity_type = 'tournament' AND tournament_id IS NOT NULL AND event_id IS NULL AND set_id IS NULL AND entrant_id IS NULL)
        OR (entity_type = 'event' AND event_id IS NOT NULL AND tournament_id IS NULL AND set_id IS NULL AND entrant_id IS NULL)
        OR (entity_type = 'set' AND set_id IS NOT NULL AND tournament_id IS NULL AND event_id IS NULL AND entrant_id IS NULL)
        OR (entity_type = 'entrant' AND entrant_id IS NOT NULL AND tournament_id IS NULL AND event_id IS NULL AND set_id IS NULL)""",
            name="mapping_target",
        ),
    )
