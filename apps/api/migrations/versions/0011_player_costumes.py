"""Costume (1-8) each player uses per character, for share images (Mission 14)."""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE players ADD COLUMN costumes JSONB NOT NULL DEFAULT '{}'::jsonb")


def downgrade():
    op.execute("ALTER TABLE players DROP COLUMN costumes")
