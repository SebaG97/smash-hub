"""Local copy of start.gg's competitive data (SH-SYNC-01, ADR-022).

start.gg stays the official source: these tables only keep what it answered last, under
start.gg's own IDs and relations, so previews, pools and brackets read PostgreSQL instead
of waiting on start.gg during a visit. Nothing is deleted because start.gg failed or
answered partially: a row start.gg stops listing after a complete, validated answer (a
withdrawn entrant, a seed moved out of a phase, a rebuilt pool) is only marked inactive.

These tables are apart from the community's canonical results (competitions, ADR-007):
registrations in progress never feed statistics, rankings or the Prode.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)

from app.database.base import Base, Record


class Stamped:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StartggTournament(Stamped, Base):
    __tablename__ = "startgg_tournaments"
    id = Column(String(40), primary_key=True)
    # Without the "tournament/" prefix, as the web's /previa/<slug> uses it.
    slug = Column(String(160), nullable=False, unique=True)
    name = Column(String(300), nullable=False)
    start_at = Column(DateTime(timezone=True))
    end_at = Column(DateTime(timezone=True))
    # start.gg's ActivityState: 1 created, 2 active, 3 completed.
    state = Column(Integer)
    city = Column(String(120))
    venue = Column(String(200))
    country_code = Column(String(2))
    attendees = Column(Integer)
    is_online = Column(Boolean)
    images = Column(JSON)
    # Synced on schedule while tracked; why it is: calendar, seeding or manual.
    tracked = Column(Boolean, nullable=False, server_default=text("true"))
    track_reason = Column(String(20), nullable=False)
    # Listed by start.gg's upcoming tournaments of the country in the last discovery.
    in_calendar = Column(Boolean, nullable=False, server_default=text("false"))
    next_sync_at = Column(DateTime(timezone=True), index=True)
    last_attempt_at = Column(DateTime(timezone=True))
    last_success_at = Column(DateTime(timezone=True))
    last_status = Column(String(20))
    last_error = Column(String(80))
    failures = Column(Integer, nullable=False, server_default=text("0"))
    __table_args__ = (
        CheckConstraint("track_reason IN ('calendar','seeding','manual')", name="track_reason"),
        CheckConstraint(
            "last_status IS NULL OR last_status IN ('completed','failed')", name="last_status"
        ),
        CheckConstraint("failures >= 0", name="failures"),
    )


class StartggEvent(Stamped, Base):
    __tablename__ = "startgg_events"
    id = Column(String(40), primary_key=True)
    tournament_id = Column(
        String(40), ForeignKey("startgg_tournaments.id"), nullable=False, index=True
    )
    # Full start.gg path: tournament/<t>/event/<e>, as seeding projects keep it.
    slug = Column(String(300), index=True)
    name = Column(String(300), nullable=False)
    videogame_id = Column(String(20))
    is_online = Column(Boolean)
    start_at = Column(DateTime(timezone=True))
    state = Column(String(20))
    num_entrants = Column(Integer)
    team_max_players = Column(Integer)
    # When each part of the event was last copied completely (None: never).
    entrants_synced_at = Column(DateTime(timezone=True))
    active = Column(Boolean, nullable=False, server_default=text("true"))
    last_seen_at = Column(DateTime(timezone=True), nullable=False)


class StartggEntrant(Stamped, Base):
    """A registration in an event (start.gg Entrant)."""

    __tablename__ = "startgg_entrants"
    id = Column(String(40), primary_key=True)
    event_id = Column(String(40), ForeignKey("startgg_events.id"), nullable=False, index=True)
    name = Column(String(300), nullable=False)
    initial_seed = Column(Integer)
    # False once start.gg stops listing it (a withdrawal); True again if it comes back.
    active = Column(Boolean, nullable=False, server_default=text("true"))
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    removed_at = Column(DateTime(timezone=True))


class StartggEntrantMember(Stamped, Base):
    """A participant of an entrant: one for singles, two for doubles.

    player_id is start.gg's global Player.id, the only identity used to match hub players
    (ExternalIdentity "player:<id>"); the gamer tag is display only, never a key.
    """

    __tablename__ = "startgg_entrant_members"
    entrant_id = Column(String(40), ForeignKey("startgg_entrants.id"), primary_key=True)
    position = Column(Integer, primary_key=True)
    participant_id = Column(String(40))
    player_id = Column(String(40), index=True)
    gamer_tag = Column(String(120))
    prefix = Column(String(120))
    country = Column(String(80))


class StartggSyncRun(Record, Base):
    """One sync attempt, automatic or manual: result, error and what changed."""

    __tablename__ = "startgg_sync_runs"
    tournament_id = Column(String(40), ForeignKey("startgg_tournaments.id"), index=True)
    # Tournament slug asked for (kept even when start.gg did not find it).
    slug = Column(String(160))
    kind = Column(String(20), nullable=False)
    trigger = Column(String(20), nullable=False)
    actor = Column(String(60), nullable=False)
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    counts = Column(JSON)
    warnings = Column(JSON)
    error_code = Column(String(80))
    __table_args__ = (
        CheckConstraint("kind IN ('tournament','discovery')", name="kind"),
        CheckConstraint("trigger IN ('auto','manual')", name="trigger"),
        CheckConstraint("status IN ('running','completed','failed')", name="status"),
        Index("ix_startgg_sync_runs_status_started_at", "status", "started_at"),
    )
