from sqlalchemy import (
    JSON, CheckConstraint, Column, DateTime, Float, ForeignKey, ForeignKeyConstraint,
    Integer, String, UniqueConstraint, Uuid,
)

from app.database.base import Base, Record


class RatingPolicy(Record, Base):
    __tablename__ = "rating_policies"
    version = Column(String(80), nullable=False, unique=True)
    parameters = Column(JSON, nullable=False)


class RatingPool(Record, Base):
    __tablename__ = "rating_pools"
    slug = Column(String(120), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    game_id = Column(Uuid, ForeignKey("games.id"), nullable=False, index=True)
    community_id = Column(Uuid, ForeignKey("communities.id"), nullable=False, index=True)
    policy_id = Column(Uuid, ForeignKey("rating_policies.id"), nullable=False)
    mode = Column(String(20), nullable=False, default="singles")
    # Explicit event allowlist; empty means NO events, never all events.
    event_ids = Column(JSON, nullable=False, default=list)
    # null = any unambiguous participant in allowed events; [] = nobody.
    player_ids = Column(JSON)
    published_run_id = Column(Uuid, ForeignKey("rating_calculation_runs.id", use_alter=True, name="fk_pool_published_run"))
    __table_args__ = (CheckConstraint("mode IN ('singles','doubles')", name="pool_mode"),)


class RatingCalculationRun(Record, Base):
    __tablename__ = "rating_calculation_runs"
    pool_id = Column(Uuid, ForeignKey("rating_pools.id"), nullable=False, index=True)
    policy_id = Column(Uuid, ForeignKey("rating_policies.id"), nullable=False)
    policy_version = Column(String(80), nullable=False)
    algorithm_version = Column(String(80), nullable=False)
    parameters = Column(JSON, nullable=False)
    input_hash = Column(String(64))
    status = Column(String(20), nullable=False)
    interval_start = Column(DateTime(timezone=True))
    interval_end = Column(DateTime(timezone=True), nullable=False)
    requested_from = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    player_count = Column(Integer, nullable=False, default=0)
    set_count = Column(Integer, nullable=False, default=0)
    excluded_undated = Column(Integer, nullable=False, default=0)
    error = Column(String(200))
    __table_args__ = (
        UniqueConstraint("pool_id", "input_hash"),
        UniqueConstraint("id", "pool_id"),
        CheckConstraint("status IN ('RUNNING','COMPLETED','FAILED')", name="run_status"),
    )


class RatingPeriod(Record, Base):
    __tablename__ = "rating_periods"
    pool_id = Column(Uuid, ForeignKey("rating_pools.id"), nullable=False, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("pool_id", "starts_at", "ends_at"),
        UniqueConstraint("id", "pool_id"),
        CheckConstraint("ends_at > starts_at", name="period_bounds"),
    )


class RatingSnapshot(Record, Base):
    __tablename__ = "rating_snapshots"
    run_id = Column(Uuid, nullable=False, index=True)
    pool_id = Column(Uuid, nullable=False, index=True)
    period_id = Column(Uuid, nullable=False, index=True)
    player_id = Column(Uuid, ForeignKey("players.id"), nullable=False, index=True)
    rating = Column(Float, nullable=False)
    rd = Column(Float, nullable=False)
    volatility = Column(Float, nullable=False)
    period_sets = Column(Integer, nullable=False)
    cumulative_sets = Column(Integer, nullable=False)
    last_activity = Column(DateTime(timezone=True))
    calculated_at = Column(DateTime(timezone=True), nullable=False)
    policy_version = Column(String(80), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["run_id", "pool_id"], ["rating_calculation_runs.id", "rating_calculation_runs.pool_id"]),
        ForeignKeyConstraint(["period_id", "pool_id"], ["rating_periods.id", "rating_periods.pool_id"]),
        UniqueConstraint("run_id", "period_id", "player_id"),
        UniqueConstraint("id", "run_id", "pool_id", "period_id"),
        CheckConstraint("rd > 0 AND rd < 'Infinity'::float8 AND volatility > 0 AND volatility < 'Infinity'::float8 AND rating > '-Infinity'::float8 AND rating < 'Infinity'::float8", name="finite_rating"),
        CheckConstraint("period_sets >= 0 AND cumulative_sets >= period_sets", name="snapshot_counts"),
    )


class RankingSnapshot(Record, Base):
    __tablename__ = "ranking_snapshots"
    rating_snapshot_id = Column(Uuid, nullable=False, unique=True)
    run_id = Column(Uuid, nullable=False, index=True)
    pool_id = Column(Uuid, nullable=False, index=True)
    period_id = Column(Uuid, nullable=False, index=True)
    status = Column(String(20), nullable=False)
    position = Column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["rating_snapshot_id", "run_id", "pool_id", "period_id"], ["rating_snapshots.id", "rating_snapshots.run_id", "rating_snapshots.pool_id", "rating_snapshots.period_id"]),
        UniqueConstraint("run_id", "period_id", "status", "position"),
        CheckConstraint("status IN ('ACTIVE','PROVISIONAL','INACTIVE')", name="ranking_status"),
        CheckConstraint("position > 0", name="ranking_position"),
    )
