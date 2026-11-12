"""Achievement storage (SH-ACH-01, migration 0024).

Prode achievements stay in prode_achievements (accounts). Player achievements live here.
Nothing is deleted to be rebuilt: the evaluator inserts what is new, revokes what no
longer holds and reactivates what holds again, keeping the first recognition date.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)

from app.database.base import Base, Record


class PlayerAchievement(Record, Base):
    __tablename__ = "player_achievements"
    __table_args__ = (
        UniqueConstraint("player_id", "achievement_id", "occurrence"),
        CheckConstraint("source IN ('auto','manual')", name="source"),
        CheckConstraint("status IN ('active','revoked')", name="status"),
    )
    player_id = Column(Uuid, ForeignKey("players.id"), nullable=False, index=True)
    achievement_id = Column(String(40), nullable=False, index=True)
    # What makes one award unique: '' for once-per-player achievements.
    occurrence = Column(String(80), nullable=False, server_default="")
    event_at = Column(DateTime(timezone=True))  # when it happened, when known
    recognized_at = Column(DateTime(timezone=True), nullable=False)  # never rewritten
    backfilled = Column(Boolean, nullable=False, server_default=text("false"))
    tournament_id = Column(Uuid)
    event_id = Column(Uuid)
    set_id = Column(Uuid)
    opponent_player_id = Column(Uuid)
    evidence = Column(JSON, nullable=False, server_default=text("'{}'"))
    source = Column(String(10), nullable=False, server_default="auto")
    granted_by = Column(String(60))
    reason = Column(String(500))
    rule_version = Column(Integer, nullable=False, server_default="1")
    status = Column(String(10), nullable=False, server_default="active")
    revoked_at = Column(DateTime(timezone=True))
    revoked_reason = Column(String(200))
    # The owner may hide any of their achievements from public pages.
    hidden = Column(Boolean, nullable=False, server_default=text("false"))


class AchievementStat(Base):
    """Holders and eligible universe per achievement, refreshed after each evaluation."""

    __tablename__ = "achievement_stats"
    achievement_id = Column(String(40), primary_key=True)
    holders = Column(Integer, nullable=False)
    universe = Column(Integer)
    coverage = Column(Float)  # share of eligible sets with the data the rule needs
    first_event_at = Column(DateTime(timezone=True))
    first_holders = Column(JSON, nullable=False, server_default=text("'[]'"))
    first_verified = Column(Boolean, nullable=False, server_default=text("false"))
    computed_at = Column(DateTime(timezone=True), nullable=False)


class AchievementSubject(Base):
    """A real person a collection is about (spike, vbash), by start.gg player id, with
    their consent. Without consent and activation the collection is never evaluated."""

    __tablename__ = "achievement_subjects"
    key = Column(String(20), primary_key=True)
    player_id = Column(Uuid, ForeignKey("players.id"), nullable=False)
    startgg_player_id = Column(String(20), nullable=False)
    consent_at = Column(DateTime(timezone=True))
    active = Column(Boolean, nullable=False, server_default=text("false"))
    set_by = Column(String(60), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AchievementRun(Record, Base):
    __tablename__ = "achievement_runs"
    trigger = Column(String(20), nullable=False)
    actor = Column(String(60), nullable=False)
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    counts = Column(JSON)
    error = Column(String(200))


class AchievementAudit(Record, Base):
    """Append-only: manual grants and revocations, subjects, recalculations."""

    __tablename__ = "achievement_audit"
    action = Column(String(30), nullable=False)
    actor = Column(String(60), nullable=False)
    achievement_id = Column(String(40))
    player_id = Column(Uuid)
    details = Column(JSON, nullable=False)


class UserShowcase(Base):
    """Up to three achievements an account owner chose to feature."""

    __tablename__ = "user_showcase"
    __table_args__ = (
        CheckConstraint("slot BETWEEN 1 AND 3", name="slot"),
        CheckConstraint("source IN ('player','prode')", name="source"),
    )
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    slot = Column(Integer, primary_key=True)
    achievement_id = Column(String(40), nullable=False)
    source = Column(String(10), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
