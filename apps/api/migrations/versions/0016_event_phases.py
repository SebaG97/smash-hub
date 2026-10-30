"""Phase names of each event from start.gg, for its bracket (Mission 25)."""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    # NULL: not read from start.gg yet; {}: nothing to read.
    op.execute("ALTER TABLE events ADD COLUMN phases JSON")


def downgrade():
    op.execute("ALTER TABLE events DROP COLUMN phases")
