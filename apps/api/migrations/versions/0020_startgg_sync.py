"""Local copy of start.gg tournaments, events and registrations, and the sync log
(SH-SYNC-01 stage 1, ADR-022).

Additive only: five new tables, nothing existing is altered.
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def stamps():
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade():
    op.create_table(
        "startgg_tournaments",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.Integer(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("venue", sa.String(length=200), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("attendees", sa.Integer(), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=True),
        sa.Column("images", sa.JSON(), nullable=True),
        sa.Column("tracked", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("track_reason", sa.String(length=20), nullable=False),
        sa.Column("in_calendar", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("last_error", sa.String(length=80), nullable=True),
        sa.Column("failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
        *stamps(),
        sa.CheckConstraint(
            "track_reason IN ('calendar','seeding','manual')",
            name=op.f("ck_startgg_tournaments_track_reason"),
        ),
        sa.CheckConstraint(
            "last_status IS NULL OR last_status IN ('completed','failed')",
            name=op.f("ck_startgg_tournaments_last_status"),
        ),
        sa.CheckConstraint("failures >= 0", name=op.f("ck_startgg_tournaments_failures")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_startgg_tournaments")),
        sa.UniqueConstraint("slug", name=op.f("uq_startgg_tournaments_slug")),
    )
    op.create_index(
        op.f("ix_startgg_tournaments_next_sync_at"), "startgg_tournaments", ["next_sync_at"]
    )
    op.create_table(
        "startgg_events",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("tournament_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=300), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("videogame_id", sa.String(length=20), nullable=True),
        sa.Column("is_online", sa.Boolean(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=True),
        sa.Column("num_entrants", sa.Integer(), nullable=True),
        sa.Column("team_max_players", sa.Integer(), nullable=True),
        sa.Column("entrants_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        *stamps(),
        sa.ForeignKeyConstraint(
            ["tournament_id"],
            ["startgg_tournaments.id"],
            name=op.f("fk_startgg_events_tournament_id_startgg_tournaments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_startgg_events")),
    )
    op.create_index(op.f("ix_startgg_events_tournament_id"), "startgg_events", ["tournament_id"])
    op.create_index(op.f("ix_startgg_events_slug"), "startgg_events", ["slug"])
    op.create_table(
        "startgg_entrants",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("initial_seed", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        *stamps(),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["startgg_events.id"],
            name=op.f("fk_startgg_entrants_event_id_startgg_events"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_startgg_entrants")),
    )
    op.create_index(op.f("ix_startgg_entrants_event_id"), "startgg_entrants", ["event_id"])
    op.create_table(
        "startgg_entrant_members",
        sa.Column("entrant_id", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.String(length=40), nullable=True),
        sa.Column("player_id", sa.String(length=40), nullable=True),
        sa.Column("gamer_tag", sa.String(length=120), nullable=True),
        sa.Column("prefix", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=80), nullable=True),
        *stamps(),
        sa.ForeignKeyConstraint(
            ["entrant_id"],
            ["startgg_entrants.id"],
            name=op.f("fk_startgg_entrant_members_entrant_id_startgg_entrants"),
        ),
        sa.PrimaryKeyConstraint("entrant_id", "position", name=op.f("pk_startgg_entrant_members")),
    )
    op.create_index(
        op.f("ix_startgg_entrant_members_player_id"), "startgg_entrant_members", ["player_id"]
    )
    op.create_table(
        "startgg_sync_runs",
        sa.Column("tournament_id", sa.String(length=40), nullable=True),
        sa.Column("slug", sa.String(length=160), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counts", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *stamps(),
        sa.CheckConstraint(
            "kind IN ('tournament','discovery')", name=op.f("ck_startgg_sync_runs_kind")
        ),
        sa.CheckConstraint(
            "trigger IN ('auto','manual')", name=op.f("ck_startgg_sync_runs_trigger")
        ),
        sa.CheckConstraint(
            "status IN ('running','completed','failed')", name=op.f("ck_startgg_sync_runs_status")
        ),
        sa.ForeignKeyConstraint(
            ["tournament_id"],
            ["startgg_tournaments.id"],
            name=op.f("fk_startgg_sync_runs_tournament_id_startgg_tournaments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_startgg_sync_runs")),
    )
    op.create_index(
        op.f("ix_startgg_sync_runs_tournament_id"), "startgg_sync_runs", ["tournament_id"]
    )
    op.create_index(
        "ix_startgg_sync_runs_status_started_at", "startgg_sync_runs", ["status", "started_at"]
    )


def downgrade():
    op.drop_index("ix_startgg_sync_runs_status_started_at", table_name="startgg_sync_runs")
    op.drop_index(op.f("ix_startgg_sync_runs_tournament_id"), table_name="startgg_sync_runs")
    op.drop_table("startgg_sync_runs")
    op.drop_index(
        op.f("ix_startgg_entrant_members_player_id"), table_name="startgg_entrant_members"
    )
    op.drop_table("startgg_entrant_members")
    op.drop_index(op.f("ix_startgg_entrants_event_id"), table_name="startgg_entrants")
    op.drop_table("startgg_entrants")
    op.drop_index(op.f("ix_startgg_events_slug"), table_name="startgg_events")
    op.drop_index(op.f("ix_startgg_events_tournament_id"), table_name="startgg_events")
    op.drop_table("startgg_events")
    op.drop_index(op.f("ix_startgg_tournaments_next_sync_at"), table_name="startgg_tournaments")
    op.drop_table("startgg_tournaments")
