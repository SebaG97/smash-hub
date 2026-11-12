"""Local copy of start.gg phases, pools and seeds (SH-SYNC-01 stage 2, ADR-022).

Additive only: three new tables and a nullable column on startgg_events (0020).
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
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


def seen():
    return [
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.add_column(
        "startgg_events", sa.Column("pools_synced_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "startgg_phases",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("phase_order", sa.Integer(), nullable=True),
        sa.Column("bracket_type", sa.String(length=40), nullable=True),
        sa.Column("num_seeds", sa.Integer(), nullable=True),
        sa.Column("seed_total", sa.Integer(), nullable=True),
        *seen(),
        *stamps(),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["startgg_events.id"],
            name=op.f("fk_startgg_phases_event_id_startgg_events"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_startgg_phases")),
    )
    op.create_index(op.f("ix_startgg_phases_event_id"), "startgg_phases", ["event_id"])
    op.create_table(
        "startgg_phase_groups",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("phase_id", sa.String(length=40), nullable=False),
        sa.Column("display_identifier", sa.String(length=40), nullable=True),
        *seen(),
        *stamps(),
        sa.ForeignKeyConstraint(
            ["phase_id"],
            ["startgg_phases.id"],
            name=op.f("fk_startgg_phase_groups_phase_id_startgg_phases"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_startgg_phase_groups")),
    )
    op.create_index(
        op.f("ix_startgg_phase_groups_phase_id"), "startgg_phase_groups", ["phase_id"]
    )
    op.create_table(
        "startgg_seeds",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("phase_id", sa.String(length=40), nullable=False),
        sa.Column("phase_group_id", sa.String(length=40), nullable=True),
        sa.Column("entrant_id", sa.String(length=40), nullable=True),
        sa.Column("seed_num", sa.Integer(), nullable=True),
        sa.Column("group_seed_num", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.String(length=40), nullable=True),
        sa.Column("tag", sa.String(length=300), nullable=True),
        sa.Column("origin_group_id", sa.String(length=40), nullable=True),
        sa.Column("origin_placement", sa.Integer(), nullable=True),
        *seen(),
        *stamps(),
        sa.ForeignKeyConstraint(
            ["phase_id"],
            ["startgg_phases.id"],
            name=op.f("fk_startgg_seeds_phase_id_startgg_phases"),
        ),
        sa.ForeignKeyConstraint(
            ["phase_group_id"],
            ["startgg_phase_groups.id"],
            name=op.f("fk_startgg_seeds_phase_group_id_startgg_phase_groups"),
        ),
        sa.ForeignKeyConstraint(
            ["entrant_id"],
            ["startgg_entrants.id"],
            name=op.f("fk_startgg_seeds_entrant_id_startgg_entrants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_startgg_seeds")),
    )
    op.create_index(op.f("ix_startgg_seeds_phase_id"), "startgg_seeds", ["phase_id"])
    op.create_index(op.f("ix_startgg_seeds_phase_group_id"), "startgg_seeds", ["phase_group_id"])
    op.create_index(op.f("ix_startgg_seeds_entrant_id"), "startgg_seeds", ["entrant_id"])


def downgrade():
    op.drop_index(op.f("ix_startgg_seeds_entrant_id"), table_name="startgg_seeds")
    op.drop_index(op.f("ix_startgg_seeds_phase_group_id"), table_name="startgg_seeds")
    op.drop_index(op.f("ix_startgg_seeds_phase_id"), table_name="startgg_seeds")
    op.drop_table("startgg_seeds")
    op.drop_index(op.f("ix_startgg_phase_groups_phase_id"), table_name="startgg_phase_groups")
    op.drop_table("startgg_phase_groups")
    op.drop_index(op.f("ix_startgg_phases_event_id"), table_name="startgg_phases")
    op.drop_table("startgg_phases")
    op.drop_column("startgg_events", "pools_synced_at")
