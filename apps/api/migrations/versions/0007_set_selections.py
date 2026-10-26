"""Characters used per game, from start.gg game selections (Mission 06)."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TABLE set_selections ("
        "set_id UUID NOT NULL, event_id UUID NOT NULL, game_number INTEGER NOT NULL, "
        "entrant_id UUID NOT NULL, character_id UUID NOT NULL, won BOOLEAN, "
        "id UUID NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
        "CONSTRAINT pk_set_selections PRIMARY KEY (id), "
        "CONSTRAINT fk_set_selections_set_id_sets FOREIGN KEY(set_id, event_id) "
        "REFERENCES sets (id, event_id) ON DELETE CASCADE, "
        "CONSTRAINT fk_set_selections_entrant_id_event_entrants FOREIGN KEY(entrant_id, event_id) "
        "REFERENCES event_entrants (id, event_id), "
        "CONSTRAINT fk_set_selections_character_id_characters FOREIGN KEY(character_id) "
        "REFERENCES characters (id), "
        "CONSTRAINT uq_set_selections_set_id_game_number_entrant_id "
        "UNIQUE (set_id, game_number, entrant_id), "
        "CONSTRAINT ck_set_selections_game_number CHECK (game_number >= 1))"
    )
    op.execute("CREATE INDEX ix_set_selections_set_id ON set_selections (set_id)")
    op.execute("CREATE INDEX ix_set_selections_entrant_id ON set_selections (entrant_id)")
    op.execute("CREATE INDEX ix_set_selections_character_id ON set_selections (character_id)")


def downgrade():
    op.execute("DROP TABLE set_selections")
