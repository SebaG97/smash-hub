"""Organizer flag for tournaments whose start.gg seeding was wrong (Mission 17)."""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE tournaments ADD COLUMN seeding_reliable BOOLEAN DEFAULT true NOT NULL")
    op.execute("ALTER TABLE tournaments ADD COLUMN seeding_flag_actor VARCHAR(60)")
    op.execute("ALTER TABLE tournaments ADD COLUMN seeding_flag_at TIMESTAMP WITH TIME ZONE")


def downgrade():
    op.execute("ALTER TABLE tournaments DROP COLUMN seeding_flag_at")
    op.execute("ALTER TABLE tournaments DROP COLUMN seeding_flag_actor")
    op.execute("ALTER TABLE tournaments DROP COLUMN seeding_reliable")
