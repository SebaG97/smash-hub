"""Seeding and ranking workspaces built from start.gg data (ADR-011, ADR-012).

A "seeding" project is one external event: its dataset is the start.gg ego-network of the
event's entrants. A "ranking" project is a country circuit: every set of the offline singles
events held there in a period. Both are kept apart from the community's canonical results.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)

from app.database.base import Base, Record


class SeedingProject(Record, Base):
    __tablename__ = "seeding_projects"
    slug = Column(String(120), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    kind = Column(String(20), nullable=False, default="seeding", server_default="seeding")
    # Ranking projects: ISO country whose offline events form the circuit.
    country_code = Column(String(2))
    startgg_event_id = Column(String(40))
    startgg_event_slug = Column(String(300))
    startgg_videogame_id = Column(String(40), nullable=False)
    # Seeding: the event day. Ranking: end of the period (exclusive).
    event_date = Column(DateTime(timezone=True), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    data_cutoff = Column(DateTime(timezone=True))
    # {"other start.gg player id": "entrant player id"}: approved identity merges.
    merges = Column(JSON, nullable=False, default=dict)
    # {"duplicate entrant player id": "kept entrant player id"}: excluded from seeding.
    duplicates = Column(JSON, nullable=False, default=dict)
    current_run_id = Column(
        Uuid, ForeignKey("seeding_runs.id", use_alter=True, name="fk_seeding_project_run")
    )
    refresh_status = Column(String(20), nullable=False, default="IDLE")
    refresh_started_at = Column(DateTime(timezone=True))
    refresh_progress = Column(JSON)
    refresh_error = Column(String(80))
    __table_args__ = (
        CheckConstraint("refresh_status IN ('IDLE','RUNNING','FAILED')", name="refresh_status"),
        CheckConstraint("event_date > window_start", name="window_bounds"),
        CheckConstraint(
            "(kind = 'seeding' AND startgg_event_id IS NOT NULL)"
            " OR (kind = 'ranking' AND country_code IS NOT NULL)",
            name="project_kind",
        ),
    )


class SeedingEntrant(Record, Base):
    __tablename__ = "seeding_entrants"
    project_id = Column(
        Uuid, ForeignKey("seeding_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    startgg_entrant_id = Column(String(40), nullable=False)
    startgg_player_id = Column(String(40), nullable=False)
    gamer_tag = Column(String(120), nullable=False)
    prefix = Column(String(120))
    profile_country = Column(String(80))
    __table_args__ = (
        UniqueConstraint("project_id", "startgg_player_id"),
        UniqueConstraint("project_id", "startgg_entrant_id"),
    )


class SeedingSet(Record, Base):
    __tablename__ = "seeding_sets"
    project_id = Column(
        Uuid, ForeignKey("seeding_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    startgg_set_id = Column(String(40), nullable=False)
    played_at = Column(DateTime(timezone=True), nullable=False)
    startgg_event_id = Column(String(40), nullable=False)
    tournament_name = Column(String(300), nullable=False)
    tournament_slug = Column(String(300))
    event_entrants = Column(Integer)
    online = Column(Boolean, nullable=False)
    country = Column(String(8))
    p1_player_id = Column(String(40))
    p1_tag = Column(String(200))
    p1_placement = Column(Integer)
    p2_player_id = Column(String(40))
    p2_tag = Column(String(200))
    p2_placement = Column(Integer)
    winner_player_id = Column(String(40))
    classification = Column(String(40), nullable=False)
    counted = Column(Boolean, nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "startgg_set_id"),)


class SeedingRun(Record, Base):
    __tablename__ = "seeding_runs"
    project_id = Column(
        Uuid, ForeignKey("seeding_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    algorithm_version = Column(String(80), nullable=False)
    parameters = Column(JSON, nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    data_cutoff = Column(DateTime(timezone=True))
    set_count = Column(Integer, nullable=False)
    event_count = Column(Integer, nullable=False)
    offline_event_count = Column(Integer, nullable=False)
    player_count = Column(Integer, nullable=False)
    actor = Column(String(60), nullable=False)


class SeedingResult(Record, Base):
    __tablename__ = "seeding_results"
    run_id = Column(
        Uuid, ForeignKey("seeding_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    startgg_player_id = Column(String(40), nullable=False)
    gamer_tag = Column(String(120), nullable=False)
    seed_algorithm = Column(Integer, nullable=False)
    metrics = Column(JSON, nullable=False)
    reasons = Column(JSON, nullable=False)
    flags = Column(JSON, nullable=False)
    __table_args__ = (
        UniqueConstraint("run_id", "startgg_player_id"),
        UniqueConstraint("run_id", "seed_algorithm"),
    )


class SeedingOverride(Record, Base):
    __tablename__ = "seeding_overrides"
    project_id = Column(
        Uuid, ForeignKey("seeding_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    startgg_player_id = Column(String(40), nullable=False)
    seed = Column(Integer, nullable=False)
    reason = Column(String(300), nullable=False)
    actor = Column(String(60), nullable=False)
    __table_args__ = (
        UniqueConstraint("project_id", "startgg_player_id"),
        CheckConstraint("seed >= 1", name="positive_seed"),
    )


class SeedingAuditEntry(Record, Base):
    """Append-only: the application never updates or deletes these rows."""

    __tablename__ = "seeding_audit_entries"
    project_id = Column(
        Uuid, ForeignKey("seeding_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action = Column(String(40), nullable=False)
    actor = Column(String(60), nullable=False)
    details = Column(JSON, nullable=False)
