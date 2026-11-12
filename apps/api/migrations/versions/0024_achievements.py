"""Achievements (SH-ACH-01): player achievements with history, stats, subjects, runs,
audit and showcase; additive columns on prode_achievements.

Additive: new tables and nullable (or defaulted) columns. No data is changed: if
achievements across contests (same user and kind, contest NULL) are duplicated, the
migration stops with an error before the new unique index instead of deleting rows.
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def _stamps():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
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
        "player_achievements",
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("achievement_id", sa.String(length=40), nullable=False),
        sa.Column("occurrence", sa.String(length=80), server_default="", nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recognized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("backfilled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("tournament_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("set_id", sa.Uuid(), nullable=True),
        sa.Column("opponent_player_id", sa.Uuid(), nullable=True),
        sa.Column("evidence", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("source", sa.String(length=10), server_default="auto", nullable=False),
        sa.Column("granted_by", sa.String(length=60), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("rule_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=200), nullable=True),
        sa.Column("hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_stamps(),
        sa.CheckConstraint(
            "source IN ('auto','manual')", name=op.f("ck_player_achievements_source")
        ),
        sa.CheckConstraint(
            "status IN ('active','revoked')", name=op.f("ck_player_achievements_status")
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], name=op.f("fk_player_achievements_player_id_players")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_player_achievements")),
        sa.UniqueConstraint(
            "player_id",
            "achievement_id",
            "occurrence",
            name=op.f("uq_player_achievements_player_id_achievement_id_occurrence"),
        ),
    )
    op.create_index(op.f("ix_player_achievements_player_id"), "player_achievements", ["player_id"])
    op.create_index(
        op.f("ix_player_achievements_achievement_id"), "player_achievements", ["achievement_id"]
    )
    op.create_table(
        "achievement_stats",
        sa.Column("achievement_id", sa.String(length=40), nullable=False),
        sa.Column("holders", sa.Integer(), nullable=False),
        sa.Column("universe", sa.Integer(), nullable=True),
        sa.Column("coverage", sa.Float(), nullable=True),
        sa.Column("first_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_holders", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("first_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("achievement_id", name=op.f("pk_achievement_stats")),
    )
    op.create_table(
        "achievement_subjects",
        sa.Column("key", sa.String(length=20), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("startgg_player_id", sa.String(length=20), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("set_by", sa.String(length=60), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], name=op.f("fk_achievement_subjects_player_id_players")
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_achievement_subjects")),
    )
    op.create_table(
        "achievement_runs",
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("actor", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counts", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(length=200), nullable=True),
        *_stamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_achievement_runs")),
    )
    op.create_table(
        "achievement_audit",
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("actor", sa.String(length=60), nullable=False),
        sa.Column("achievement_id", sa.String(length=40), nullable=True),
        sa.Column("player_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        *_stamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_achievement_audit")),
    )
    op.create_table(
        "user_showcase",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("achievement_id", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("slot BETWEEN 1 AND 3", name=op.f("ck_user_showcase_slot")),
        sa.CheckConstraint("source IN ('player','prode')", name=op.f("ck_user_showcase_source")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_showcase_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "slot", name=op.f("pk_user_showcase")),
    )
    op.add_column(
        "prode_achievements", sa.Column("event_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("prode_achievements", sa.Column("evidence", sa.JSON(), nullable=True))
    op.add_column(
        "prode_achievements",
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
    )
    op.add_column(
        "prode_achievements", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "prode_achievements",
        sa.Column("hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    # Achievements across contests (contest NULL) must be unique before the index. The
    # earlier code deleted and rebuilt them, so duplicates are not expected; if any exist,
    # stop instead of deleting anything (SH-ACH-01 publication rule).
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM (SELECT user_id, kind FROM prode_achievements "
                "WHERE contest_id IS NULL GROUP BY user_id, kind HAVING count(*) > 1) d"
            )
        )
        .scalar()
    )
    if duplicates:
        raise RuntimeError(
            f"0024: {duplicates} duplicated Prode achievements across contests; "
            "nothing was changed. Review them by hand before migrating."
        )
    op.create_index(
        "uq_prode_achievements_lifetime",
        "prode_achievements",
        ["user_id", "kind"],
        unique=True,
        postgresql_where=sa.text("contest_id IS NULL"),
    )


def downgrade():
    op.drop_index("uq_prode_achievements_lifetime", table_name="prode_achievements")
    for column in ("hidden", "revoked_at", "status", "evidence", "event_at"):
        op.drop_column("prode_achievements", column)
    op.drop_table("user_showcase")
    op.drop_table("achievement_audit")
    op.drop_table("achievement_runs")
    op.drop_table("achievement_subjects")
    op.drop_table("achievement_stats")
    op.drop_index(op.f("ix_player_achievements_achievement_id"), table_name="player_achievements")
    op.drop_index(op.f("ix_player_achievements_player_id"), table_name="player_achievements")
    op.drop_table("player_achievements")
