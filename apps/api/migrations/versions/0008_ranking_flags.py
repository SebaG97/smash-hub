"""Tournament ranking flag and character icons (Mission 07)."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE tournaments ADD COLUMN counts_for_ranking BOOLEAN DEFAULT true NOT NULL"
    )
    op.execute("ALTER TABLE tournaments ADD COLUMN ranking_flag_actor VARCHAR(60)")
    op.execute("ALTER TABLE tournaments ADD COLUMN ranking_flag_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE characters ADD COLUMN image_url VARCHAR(400)")


def downgrade():
    op.execute("ALTER TABLE characters DROP COLUMN image_url")
    op.execute("ALTER TABLE tournaments DROP COLUMN ranking_flag_at")
    op.execute("ALTER TABLE tournaments DROP COLUMN ranking_flag_actor")
    op.execute("ALTER TABLE tournaments DROP COLUMN counts_for_ranking")
