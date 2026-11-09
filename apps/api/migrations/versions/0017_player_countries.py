"""Flag chosen by organizers for a start.gg player (Mission 32)."""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TABLE player_countries (\n\tstartgg_player_id VARCHAR(20) NOT NULL, "
        "\n\tcountry VARCHAR(2) NOT NULL, \n\tactor VARCHAR(60), "
        "\n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "\n\tCONSTRAINT pk_player_countries PRIMARY KEY (startgg_player_id), "
        "\n\tCONSTRAINT ck_player_countries_country CHECK (country ~ '^[A-Z]{2}$')\n)"
    )


def downgrade():
    op.execute("DROP TABLE player_countries")
