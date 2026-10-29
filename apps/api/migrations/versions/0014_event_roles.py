"""Main and secondary events of a tournament (Mission 20)."""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    # NULL: decided by the automatic rule; true/false: an organizer's decision.
    op.execute("ALTER TABLE events ADD COLUMN main BOOLEAN")
    op.execute("ALTER TABLE events ADD COLUMN main_flag_actor VARCHAR(60)")
    op.execute("ALTER TABLE events ADD COLUMN main_flag_at TIMESTAMP WITH TIME ZONE")


def downgrade():
    op.execute("ALTER TABLE events DROP COLUMN main_flag_at")
    op.execute("ALTER TABLE events DROP COLUMN main_flag_actor")
    op.execute("ALTER TABLE events DROP COLUMN main")
