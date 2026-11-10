"""Prode: predictions on upcoming tournaments (Mission SH-PRODE-01, ADR-020).

Players are referenced by their start.gg id, like the preview, so foreign entrants the hub
has never imported can be picked too. Scores and achievements are derived: settling a
contest deletes and rebuilds them, so settling twice changes nothing.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)

from app.database.base import Base, Record


class ProdeContest(Record, Base):
    __tablename__ = "prode_contests"
    tournament_slug = Column(String(160), nullable=False)
    startgg_event_id = Column(String(20), nullable=False)
    startgg_event_slug = Column(String(200), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    event_name = Column(String(200))
    # open → locked → settled; void cancels it.
    status = Column(String(20), nullable=False, server_default="open")
    locks_at = Column(DateTime(timezone=True))
    locked_at = Column(DateTime(timezone=True))
    settled_at = Column(DateTime(timezone=True))
    # Points travel with the contest: changing the defaults never rewrites past contests.
    rules = Column(JSON, nullable=False)
    rules_version = Column(Integer, nullable=False, server_default="1")
    created_by = Column(String(60), nullable=False)


class ProdeCandidate(Record, Base):
    """Entrants who can be picked, kept in sync with start.gg while the contest is open."""

    __tablename__ = "prode_candidates"
    __table_args__ = (UniqueConstraint("contest_id", "startgg_player_id"),)
    contest_id = Column(
        Uuid, ForeignKey("prode_contests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    startgg_player_id = Column(String(20), nullable=False)
    startgg_entrant_id = Column(String(20))
    tag = Column(String(120), nullable=False)
    prefix = Column(String(80))
    seed = Column(Integer)
    withdrawn_at = Column(DateTime(timezone=True))


class ProdeQuestion(Record, Base):
    """One thing to predict: champion, runner_up, top8."""

    __tablename__ = "prode_questions"
    __table_args__ = (UniqueConstraint("contest_id", "kind"),)
    contest_id = Column(
        Uuid, ForeignKey("prode_contests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind = Column(String(30), nullable=False)
    # open, settled or void.
    status = Column(String(20), nullable=False, server_default="open")
    result = Column(JSON)
    result_source = Column(String(20))
    settled_at = Column(DateTime(timezone=True))


class ProdePrediction(Record, Base):
    __tablename__ = "prode_predictions"
    __table_args__ = (UniqueConstraint("question_id", "user_id"),)
    question_id = Column(
        Uuid, ForeignKey("prode_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(JSON, nullable=False)


class ProdePredictionHistory(Record, Base):
    """Append-only: every saved value, the application never updates or deletes these."""

    __tablename__ = "prode_prediction_history"
    prediction_id = Column(
        Uuid, ForeignKey("prode_predictions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value = Column(JSON, nullable=False)


class ProdeScore(Record, Base):
    __tablename__ = "prode_scores"
    __table_args__ = (UniqueConstraint("contest_id", "user_id"),)
    contest_id = Column(
        Uuid, ForeignKey("prode_contests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    points = Column(Integer, nullable=False)
    exact_hits = Column(Integer, nullable=False)
    hits = Column(Integer, nullable=False)
    picks = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=False)
    last_saved_at = Column(DateTime(timezone=True))


class ProdeAchievement(Record, Base):
    """The Prode's prize: achievements on the forecaster's profile (and player profile)."""

    __tablename__ = "prode_achievements"
    __table_args__ = (UniqueConstraint("user_id", "contest_id", "kind"),)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Null for achievements across contests ("Habitué del Prode").
    contest_id = Column(
        Uuid, ForeignKey("prode_contests.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind = Column(String(40), nullable=False)
    title = Column(String(80), nullable=False)
    detail = Column(String(240), nullable=False)
    rare = Column(Boolean, nullable=False, server_default=text("false"))


class ProdeAuditEntry(Record, Base):
    """Append-only log of what organizers did to a contest."""

    __tablename__ = "prode_audit_entries"
    contest_id = Column(
        Uuid, ForeignKey("prode_contests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action = Column(String(40), nullable=False)
    actor = Column(String(60), nullable=False)
    details = Column(JSON, nullable=False)
