"""Incremental start.gg provenance and publication; 0001 stays frozen."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "external_mappings",
        sa.Column("manual_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tournaments",
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("tournaments", sa.Column("status", sa.String(30), nullable=True))
    op.add_column("tournaments", sa.Column("location", sa.JSON(), nullable=True))
    op.add_column("tournaments", sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "players",
        sa.Column("manual_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tournament_participants", sa.Column("external_id", sa.String(200), nullable=True)
    )
    op.add_column(
        "tournament_participants",
        sa.Column("manual_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("events", sa.Column("status", sa.String(30), nullable=True))
    op.add_column("events", sa.Column("competition_type", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("num_entrants", sa.Integer(), nullable=True))
    op.add_column("event_entrants", sa.Column("placement", sa.Integer(), nullable=True))
    op.add_column(
        "sets",
        sa.Column("manual_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "sets",
        sa.Column(
            "ranking_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column("sets", sa.Column("source_result", sa.JSON(), nullable=True))
    op.add_column(
        "sets",
        sa.Column("result_history", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("import_jobs", sa.Column("counts", sa.JSON(), nullable=True))
    op.add_column("import_jobs", sa.Column("conflicts", sa.JSON(), nullable=True))
    op.create_check_constraint(
        "ranking_candidate",
        "sets",
        "NOT ranking_eligible OR (status = 'completed' AND completed_at IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_tournament_participants_external_id", "tournament_participants", ["external_id"]
    )
    op.drop_constraint("ck_sets_set_status", "sets")
    op.create_check_constraint(
        "set_status", "sets", "status IN ('pending','completed','dq','bye','incomplete')"
    )
    op.drop_constraint("ck_sets_completion_time", "sets")
    op.create_check_constraint(
        "completion_time", "sets", "status <> 'pending' OR completed_at IS NULL"
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION validate_set_result(target uuid) RETURNS void LANGUAGE plpgsql AS $$\nDECLARE s sets%ROWTYPE; n int; entrants int; winners int; scored int; ws int; ls int;\nBEGIN\n SELECT * INTO s FROM sets WHERE id = target FOR UPDATE;\n IF NOT FOUND THEN RETURN; END IF;\n SELECT count(*), count(entrant_id), count(*) FILTER (WHERE is_winner), count(score),\n        max(score) FILTER (WHERE is_winner), max(score) FILTER (WHERE NOT is_winner)\n INTO n, entrants, winners, scored, ws, ls FROM set_sides WHERE set_id = target;\n IF s.status = 'pending' THEN\n   IF winners <> 0 OR scored <> 0 THEN\n     RAISE EXCEPTION 'Pending set cannot have results' USING ERRCODE = '23514'; END IF;\n ELSIF s.status = 'completed' THEN\n   IF n <> 2 OR entrants <> 2 OR winners <> 1 OR scored <> 2 OR ws <= ls\n     OR (s.best_of IS NOT NULL AND (ws <> (s.best_of / 2 + 1) OR ls >= ws)) THEN\n     RAISE EXCEPTION 'Invalid completed set' USING ERRCODE = '23514'; END IF;\n ELSIF s.status = 'dq' THEN\n   IF n <> 2 OR entrants <> 2 OR winners <> 1 OR scored <> 0 THEN\n     RAISE EXCEPTION 'Invalid DQ set' USING ERRCODE = '23514'; END IF;\n ELSIF s.status = 'bye' THEN\n   IF entrants <> 1 OR winners <> 1 OR scored <> 0 THEN\n     RAISE EXCEPTION 'Invalid BYE set' USING ERRCODE = '23514'; END IF;\n END IF;\nEND $$;"
    )


def downgrade():
    op.drop_constraint("ck_sets_ranking_candidate", "sets")
    op.drop_column("external_mappings", "manual_locked")
    # Refuse lossy rollback when the old schema cannot represent imported results.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM sets WHERE status='incomplete' OR (status <> 'pending' AND completed_at IS NULL)) THEN RAISE EXCEPTION 'Resolve incomplete results before downgrade'; END IF; END $$"
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION validate_set_result(target uuid) RETURNS void LANGUAGE plpgsql AS $$\nDECLARE s sets%ROWTYPE; n int; entrants int; winners int; scored int; ws int; ls int;\nBEGIN\n SELECT * INTO s FROM sets WHERE id = target FOR UPDATE;\n IF NOT FOUND THEN RETURN; END IF;\n SELECT count(*), count(entrant_id), count(*) FILTER (WHERE is_winner), count(score),\n        max(score) FILTER (WHERE is_winner), max(score) FILTER (WHERE NOT is_winner)\n INTO n, entrants, winners, scored, ws, ls FROM set_sides WHERE set_id = target;\n IF s.status = 'pending' THEN\n   IF winners <> 0 OR scored <> 0 THEN\n     RAISE EXCEPTION 'Pending set cannot have results' USING ERRCODE = '23514'; END IF;\n ELSIF s.status = 'completed' THEN\n   IF n <> 2 OR entrants <> 2 OR winners <> 1 OR scored <> 2 OR ws <= ls\n     OR (s.best_of IS NOT NULL AND (ws <> (s.best_of / 2 + 1) OR ls >= ws)) THEN\n     RAISE EXCEPTION 'Invalid completed set' USING ERRCODE = '23514'; END IF;\n ELSIF s.status = 'dq' THEN\n   IF n <> 2 OR entrants <> 2 OR winners <> 1 OR scored <> 0 THEN\n     RAISE EXCEPTION 'Invalid DQ set' USING ERRCODE = '23514'; END IF;\n ELSIF s.status = 'bye' THEN\n   IF entrants <> 1 OR winners <> 1 OR scored <> 0 THEN\n     RAISE EXCEPTION 'Invalid BYE set' USING ERRCODE = '23514'; END IF;\n END IF;\nEND $$;"
    )
    op.drop_constraint("ck_sets_completion_time", "sets")
    op.create_check_constraint(
        "completion_time",
        "sets",
        "(status = 'pending' AND completed_at IS NULL) OR (status <> 'pending' AND completed_at IS NOT NULL)",
    )
    op.drop_constraint("ck_sets_set_status", "sets")
    op.create_check_constraint("set_status", "sets", "status IN ('pending','completed','dq','bye')")
    op.drop_constraint("uq_tournament_participants_external_id", "tournament_participants")
    op.drop_column("import_jobs", "conflicts")
    op.drop_column("import_jobs", "counts")
    op.drop_column("sets", "result_history")
    op.drop_column("sets", "source_result")
    op.drop_column("sets", "ranking_eligible")
    op.drop_column("sets", "manual_locked")
    op.drop_column("event_entrants", "placement")
    op.drop_column("events", "num_entrants")
    op.drop_column("events", "competition_type")
    op.drop_column("events", "status")
    op.drop_column("tournament_participants", "manual_locked")
    op.drop_column("tournament_participants", "external_id")
    op.drop_column("players", "manual_locked")
    op.drop_column("tournaments", "synced_at")
    op.drop_column("tournaments", "location")
    op.drop_column("tournaments", "status")
    op.drop_column("tournaments", "published")
