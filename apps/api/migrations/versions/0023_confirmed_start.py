"""Start time confirmed by organizers for a synced start.gg tournament (SH-FIX-01).

Additive only: two nullable columns on startgg_tournaments. start.gg's own start_at is
kept as received.
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "startgg_tournaments",
        sa.Column("start_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "startgg_tournaments",
        sa.Column("start_confirmed_by", sa.String(length=60), nullable=True),
    )


def downgrade():
    op.drop_column("startgg_tournaments", "start_confirmed_by")
    op.drop_column("startgg_tournaments", "start_confirmed_at")
