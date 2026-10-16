"""Classify set lifecycle separately from resolution; preserve legacy result shape."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sets",
        sa.Column("lifecycle_status", sa.String(20), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "sets", sa.Column("resolution", sa.String(24), nullable=False, server_default="unresolved")
    )
    op.add_column(
        "sets",
        sa.Column(
            "classification_reason",
            sa.String(80),
            nullable=False,
            server_default="legacy_unverified",
        ),
    )
    op.add_column(
        "sets", sa.Column("normalization_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("sets", sa.Column("round_number", sa.Integer()))
    op.add_column(
        "sets",
        sa.Column("stats_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # No unverified legacy classification may enable future statistics/ranking.
    # Reimport fills source evidence and version 2 atomically, respecting manual locks.
    op.execute(
        "UPDATE sets SET lifecycle_status=CASE WHEN status IN ('completed','dq','bye','incomplete') THEN 'completed' ELSE 'unknown' END, resolution=CASE status WHEN 'completed' THEN 'played' WHEN 'dq' THEN 'dq' WHEN 'bye' THEN 'bye' ELSE 'unresolved' END, ranking_eligible=false"
    )
    # UPDATE queues frozen 0001 constraint triggers. Validate them before ALTER.
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.create_check_constraint(
        "set_lifecycle",
        "sets",
        "lifecycle_status IN ('pending','in_progress','completed','not_played','unknown')",
    )
    op.create_check_constraint(
        "set_resolution",
        "sets",
        "resolution IN ('unresolved','played','dq','bye','placeholder','conditional_unused')",
    )
    op.create_check_constraint(
        "played_stats",
        "sets",
        "NOT stats_eligible OR (lifecycle_status = 'completed' AND resolution = 'played' AND status = 'completed')",
    )
    op.create_check_constraint(
        "ranking_requires_played", "sets", "NOT ranking_eligible OR stats_eligible"
    )

    op.execute("SET CONSTRAINTS ALL DEFERRED")


def downgrade():
    for name in ("ranking_requires_played", "played_stats", "set_resolution", "set_lifecycle"):
        op.drop_constraint("ck_sets_" + name, "sets")
    for name in (
        "stats_eligible",
        "round_number",
        "normalization_version",
        "classification_reason",
        "resolution",
        "lifecycle_status",
    ):
        op.drop_column("sets", name)
