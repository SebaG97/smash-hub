from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)

from app.database.base import Base, Record


class Tournament(Record, Base):
    __tablename__ = "tournaments"
    community_id = Column(Uuid, ForeignKey("communities.id"), nullable=False, index=True)
    slug = Column(String(160), nullable=False)
    name = Column(String(200), nullable=False)
    published = Column(Boolean, nullable=False, server_default=text("false"))
    status = Column(String(30))
    location = Column(JSON)
    # start.gg logo and banner links (Mission 19); NULL until read, {} when it has none.
    images = Column(JSON(none_as_null=True))
    # Mission 22: whether the participants' prefixes were read (imports before it did not).
    prefixes_read = Column(Boolean, nullable=False, server_default=text("false"))
    synced_at = Column(DateTime(timezone=True))
    starts_at = Column(DateTime(timezone=True))
    ends_at = Column(DateTime(timezone=True))
    # Organizer decision (Mission 07): whether its results feed the rankings.
    counts_for_ranking = Column(Boolean, nullable=False, server_default=text("true"))
    ranking_flag_actor = Column(String(60))
    ranking_flag_at = Column(DateTime(timezone=True))
    # Organizer decision (Mission 17): false when start.gg's seeds did not reflect the
    # players' level, so the event yields no upsets or "beat their seed" records.
    seeding_reliable = Column(Boolean, nullable=False, server_default=text("true"))
    seeding_flag_actor = Column(String(60))
    seeding_flag_at = Column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("community_id", "slug"),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at", name="tournament_dates"
        ),
    )


class TournamentParticipant(Record, Base):
    __tablename__ = "tournament_participants"
    tournament_id = Column(Uuid, ForeignKey("tournaments.id"), nullable=False, index=True)
    player_id = Column(Uuid, ForeignKey("players.id"), nullable=False, index=True)
    external_id = Column(String(200), unique=True)
    manual_locked = Column(Boolean, nullable=False, server_default=text("false"))
    tag_snapshot = Column(String(120), nullable=False)
    # start.gg prefix typed at this registration ("BG", "GO"…), as is (Mission 22).
    prefix = Column(String(80))
    __table_args__ = (
        UniqueConstraint("tournament_id", "player_id"),
        UniqueConstraint("id", "tournament_id"),
    )


class Event(Record, Base):
    __tablename__ = "events"
    tournament_id = Column(Uuid, ForeignKey("tournaments.id"), nullable=False, index=True)
    game_id = Column(Uuid, ForeignKey("games.id"), nullable=False, index=True)
    slug = Column(String(120), nullable=False)
    name = Column(String(200), nullable=False)
    status = Column(String(30))
    competition_type = Column(Integer)
    num_entrants = Column(Integer)
    team_size = Column(Integer, nullable=False, server_default="1")
    # Mission 20: organizer's call on whether this is the tournament's main bracket (ranking,
    # titles). NULL leaves it to the rule in app.competitions.roles.
    main = Column(Boolean)
    main_flag_actor = Column(String(60))
    main_flag_at = Column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tournament_id", "slug"),
        UniqueConstraint("id", "tournament_id"),
        CheckConstraint("team_size >= 1", name="team_size"),
    )


class EventEntrant(Record, Base):
    __tablename__ = "event_entrants"
    event_id = Column(Uuid, nullable=False, index=True)
    tournament_id = Column(Uuid, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    placement = Column(Integer)
    seed = Column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(["event_id", "tournament_id"], ["events.id", "events.tournament_id"]),
        UniqueConstraint("id", "event_id"),
        UniqueConstraint("id", "event_id", "tournament_id"),
        UniqueConstraint("event_id", "seed"),
        CheckConstraint("seed IS NULL OR seed > 0", name="positive_seed"),
    )


class EntrantMember(Record, Base):
    __tablename__ = "entrant_members"
    entrant_id = Column(Uuid, nullable=False, index=True)
    event_id = Column(Uuid, nullable=False, index=True)
    tournament_id = Column(Uuid, nullable=False, index=True)
    participant_id = Column(Uuid, nullable=False, index=True)
    position = Column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["entrant_id", "event_id", "tournament_id"],
            ["event_entrants.id", "event_entrants.event_id", "event_entrants.tournament_id"],
        ),
        ForeignKeyConstraint(
            ["participant_id", "tournament_id"],
            ["tournament_participants.id", "tournament_participants.tournament_id"],
        ),
        UniqueConstraint("event_id", "participant_id"),
        UniqueConstraint("entrant_id", "position"),
        CheckConstraint("position > 0", name="member_position"),
    )


class Set(Record, Base):
    __tablename__ = "sets"
    event_id = Column(Uuid, ForeignKey("events.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, server_default="pending")
    # Legacy result shape remains for frozen 0001/0002 integrity triggers.
    # Public state and classification use lifecycle_status/resolution below.
    lifecycle_status = Column(String(20), nullable=False, server_default="unknown")
    resolution = Column(String(24), nullable=False, server_default="unresolved")
    classification_reason = Column(String(80), nullable=False, server_default="legacy_unverified")
    normalization_version = Column(Integer, nullable=False, server_default="0")
    round_number = Column(Integer)
    stats_eligible = Column(Boolean, nullable=False, server_default=text("false"))
    manual_locked = Column(Boolean, nullable=False, server_default=text("false"))
    ranking_eligible = Column(Boolean, nullable=False, server_default=text("false"))
    source_result = Column(JSON)
    result_history = Column(JSON, nullable=False, server_default=text("'[]'"))
    round_label = Column(String(100))
    best_of = Column(Integer)
    completed_at = Column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("id", "event_id"),
        CheckConstraint(
            "status IN ('pending','completed','dq','bye','incomplete')", name="set_status"
        ),
        CheckConstraint("best_of IS NULL OR (best_of > 0 AND best_of % 2 = 1)", name="best_of"),
        CheckConstraint(
            "lifecycle_status IN ('pending','in_progress','completed','not_played','unknown')",
            name="set_lifecycle",
        ),
        CheckConstraint(
            "resolution IN ('unresolved','played','dq','bye','placeholder','conditional_unused')",
            name="set_resolution",
        ),
        CheckConstraint(
            "NOT stats_eligible OR (lifecycle_status = 'completed' AND resolution = 'played' AND status = 'completed')",
            name="played_stats",
        ),
        CheckConstraint("NOT ranking_eligible OR stats_eligible", name="ranking_requires_played"),
        CheckConstraint(
            "NOT ranking_eligible OR (status = 'completed' AND completed_at IS NOT NULL)",
            name="ranking_candidate",
        ),
        CheckConstraint(
            "status <> 'pending' OR completed_at IS NULL",
            name="completion_time",
        ),
    )


class SetSide(Record, Base):
    __tablename__ = "set_sides"
    set_id = Column(Uuid, nullable=False, index=True)
    event_id = Column(Uuid, nullable=False, index=True)
    entrant_id = Column(Uuid, index=True)
    side = Column(Integer, nullable=False)
    score = Column(Integer)
    is_winner = Column(Boolean, nullable=False, server_default=text("false"))
    __table_args__ = (
        ForeignKeyConstraint(["set_id", "event_id"], ["sets.id", "sets.event_id"]),
        ForeignKeyConstraint(
            ["entrant_id", "event_id"], ["event_entrants.id", "event_entrants.event_id"]
        ),
        UniqueConstraint("set_id", "side"),
        UniqueConstraint("set_id", "entrant_id"),
        CheckConstraint("side IN (1,2)", name="side_number"),
        CheckConstraint("score IS NULL OR score >= 0", name="nonnegative_score"),
        CheckConstraint(
            "entrant_id IS NOT NULL OR (score IS NULL AND NOT is_winner)", name="empty_side"
        ),
    )


class SetSelection(Record, Base):
    """Character an entrant used in one game of a set, as reported to start.gg."""

    __tablename__ = "set_selections"
    set_id = Column(Uuid, nullable=False, index=True)
    event_id = Column(Uuid, nullable=False)
    game_number = Column(Integer, nullable=False)
    entrant_id = Column(Uuid, nullable=False, index=True)
    character_id = Column(Uuid, ForeignKey("characters.id"), nullable=False, index=True)
    won = Column(Boolean)
    __table_args__ = (
        ForeignKeyConstraint(
            ["set_id", "event_id"], ["sets.id", "sets.event_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["entrant_id", "event_id"], ["event_entrants.id", "event_entrants.event_id"]
        ),
        UniqueConstraint("set_id", "game_number", "entrant_id"),
        CheckConstraint("game_number >= 1", name="game_number"),
    )
