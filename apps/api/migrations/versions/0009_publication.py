"""Seeding drafts and published projects (Mission 08)."""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE seeding_projects ADD COLUMN published BOOLEAN DEFAULT false NOT NULL")
    # Rankings were already public; seedings become drafts until an organizer publishes them.
    op.execute("UPDATE seeding_projects SET published = true WHERE kind = 'ranking'")


def downgrade():
    op.execute("ALTER TABLE seeding_projects DROP COLUMN published")
