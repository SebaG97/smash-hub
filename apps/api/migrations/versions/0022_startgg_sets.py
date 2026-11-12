"""Local copy of start.gg sets (SH-SYNC-01 stage 3, ADR-022).

Additive only: one new table and a nullable column on startgg_events (0020).
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "startgg_events", sa.Column("sets_synced_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "startgg_sets",
        sa.Column("id", sa.String(length=60), nullable=False),
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("phase_group_id", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=True),
        sa.Column("full_round_text", sa.String(length=120), nullable=True),
        sa.Column("state", sa.Integer(), nullable=True),
        sa.Column("winner_entrant_id", sa.String(length=40), nullable=True),
        sa.Column("display_score", sa.String(length=200), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["startgg_events.id"],
            name=op.f("fk_startgg_sets_event_id_startgg_events"),
        ),
        sa.ForeignKeyConstraint(
            ["phase_group_id"],
            ["startgg_phase_groups.id"],
            name=op.f("fk_startgg_sets_phase_group_id_startgg_phase_groups"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_startgg_sets")),
    )
    op.create_index(op.f("ix_startgg_sets_event_id"), "startgg_sets", ["event_id"])
    op.create_index(op.f("ix_startgg_sets_phase_group_id"), "startgg_sets", ["phase_group_id"])


def downgrade():
    op.drop_index(op.f("ix_startgg_sets_phase_group_id"), table_name="startgg_sets")
    op.drop_index(op.f("ix_startgg_sets_event_id"), table_name="startgg_sets")
    op.drop_table("startgg_sets")
    op.drop_column("startgg_events", "sets_synced_at")
