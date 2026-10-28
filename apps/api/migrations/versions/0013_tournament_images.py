"""Tournament logo and banner links from start.gg (Mission 19)."""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    # NULL: not read from start.gg yet; {}: start.gg has none.
    op.execute("ALTER TABLE tournaments ADD COLUMN images JSON")


def downgrade():
    op.execute("ALTER TABLE tournaments DROP COLUMN images")
