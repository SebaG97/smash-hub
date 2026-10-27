"""Recent start.gg character picks per seeding entrant (Mission 09)."""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE seeding_entrants ADD COLUMN mains JSON")


def downgrade():
    op.execute("ALTER TABLE seeding_entrants DROP COLUMN mains")
