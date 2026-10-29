"""start.gg prefixes per registration and organizers' teams (Mission 22)."""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

TEAMS = ("BG", "RN", "GO", "META", "LEGEND", "MGK")


def upgrade():
    op.execute("ALTER TABLE tournament_participants ADD COLUMN prefix VARCHAR(80)")
    # false until the participants' prefixes were read from start.gg (old imports).
    op.execute("ALTER TABLE tournaments ADD COLUMN prefixes_read BOOLEAN DEFAULT false NOT NULL")
    op.execute(
        "CREATE TABLE team_prefixes (\n\tkey VARCHAR(80) NOT NULL, \n\tstatus VARCHAR(10) NOT NULL, "
        "\n\tname VARCHAR(40) NOT NULL, \n\tteam VARCHAR(80), \n\tactor VARCHAR(60), "
        "\n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "\n\tCONSTRAINT pk_team_prefixes PRIMARY KEY (key), "
        "\n\tCONSTRAINT ck_team_prefixes_status CHECK (status IN ('team','alias','shown','hidden')), "
        "\n\tCONSTRAINT ck_team_prefixes_alias_team CHECK (status <> 'alias' OR team IS NOT NULL)\n)"
    )
    # The scene's established teams, as the organizers listed them.
    for name in TEAMS:
        op.execute(
            f"INSERT INTO team_prefixes (key, status, name, actor) "
            f"VALUES ('{name.lower()}', 'team', '{name}', 'migration')"
        )


def downgrade():
    op.execute("DROP TABLE team_prefixes")
    op.execute("ALTER TABLE tournaments DROP COLUMN prefixes_read")
    op.execute("ALTER TABLE tournament_participants DROP COLUMN prefix")
