"""Ranking projects: country circuits computed with the seeding engine (ADR-012)."""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE seeding_projects ADD COLUMN kind VARCHAR(20) DEFAULT 'seeding' NOT NULL"
    )
    op.execute("ALTER TABLE seeding_projects ADD COLUMN country_code VARCHAR(2)")
    op.execute("ALTER TABLE seeding_projects ALTER COLUMN startgg_event_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE seeding_projects ADD CONSTRAINT ck_seeding_projects_project_kind CHECK "
        "((kind = 'seeding' AND startgg_event_id IS NOT NULL)"
        " OR (kind = 'ranking' AND country_code IS NOT NULL))"
    )


def downgrade():
    op.execute("DELETE FROM seeding_projects WHERE kind = 'ranking'")
    op.execute("ALTER TABLE seeding_projects DROP CONSTRAINT ck_seeding_projects_project_kind")
    op.execute("ALTER TABLE seeding_projects ALTER COLUMN startgg_event_id SET NOT NULL")
    op.execute("ALTER TABLE seeding_projects DROP COLUMN country_code")
    op.execute("ALTER TABLE seeding_projects DROP COLUMN kind")
