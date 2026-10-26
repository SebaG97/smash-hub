"""Seeding workspace: external dataset, runs, results, overrides and audit (ADR-011)."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TABLE seeding_projects (\n\tslug VARCHAR(120) NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tstartgg_event_id VARCHAR(40) NOT NULL, \n\tstartgg_event_slug VARCHAR(300), \n\tstartgg_videogame_id VARCHAR(40) NOT NULL, \n\tevent_date TIMESTAMP WITH TIME ZONE NOT NULL, \n\twindow_start TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdata_cutoff TIMESTAMP WITH TIME ZONE, \n\tmerges JSON NOT NULL, \n\tduplicates JSON NOT NULL, \n\tcurrent_run_id UUID, \n\trefresh_status VARCHAR(20) NOT NULL, \n\trefresh_started_at TIMESTAMP WITH TIME ZONE, \n\trefresh_progress JSON, \n\trefresh_error VARCHAR(80), \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_seeding_projects PRIMARY KEY (id), \n\tCONSTRAINT ck_seeding_projects_refresh_status CHECK (refresh_status IN ('IDLE','RUNNING','FAILED')), \n\tCONSTRAINT ck_seeding_projects_window_bounds CHECK (event_date > window_start), \n\tCONSTRAINT uq_seeding_projects_slug UNIQUE (slug)\n)"
    )
    op.execute(
        "CREATE TABLE seeding_runs (\n\tproject_id UUID NOT NULL, \n\talgorithm_version VARCHAR(80) NOT NULL, \n\tparameters JSON NOT NULL, \n\twindow_start TIMESTAMP WITH TIME ZONE NOT NULL, \n\twindow_end TIMESTAMP WITH TIME ZONE NOT NULL, \n\tdata_cutoff TIMESTAMP WITH TIME ZONE, \n\tset_count INTEGER NOT NULL, \n\tevent_count INTEGER NOT NULL, \n\toffline_event_count INTEGER NOT NULL, \n\tplayer_count INTEGER NOT NULL, \n\tactor VARCHAR(60) NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_seeding_runs PRIMARY KEY (id), \n\tCONSTRAINT fk_seeding_runs_project_id_seeding_projects FOREIGN KEY(project_id) REFERENCES seeding_projects (id) ON DELETE CASCADE\n)"
    )
    op.execute("CREATE INDEX ix_seeding_runs_project_id ON seeding_runs (project_id)")
    op.execute(
        "CREATE TABLE seeding_entrants (\n\tproject_id UUID NOT NULL, \n\tstartgg_entrant_id VARCHAR(40) NOT NULL, \n\tstartgg_player_id VARCHAR(40) NOT NULL, \n\tgamer_tag VARCHAR(120) NOT NULL, \n\tprefix VARCHAR(120), \n\tprofile_country VARCHAR(80), \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_seeding_entrants PRIMARY KEY (id), \n\tCONSTRAINT uq_seeding_entrants_project_id_startgg_player_id UNIQUE (project_id, startgg_player_id), \n\tCONSTRAINT uq_seeding_entrants_project_id_startgg_entrant_id UNIQUE (project_id, startgg_entrant_id), \n\tCONSTRAINT fk_seeding_entrants_project_id_seeding_projects FOREIGN KEY(project_id) REFERENCES seeding_projects (id) ON DELETE CASCADE\n)"
    )
    op.execute("CREATE INDEX ix_seeding_entrants_project_id ON seeding_entrants (project_id)")
    op.execute(
        "CREATE TABLE seeding_sets (\n\tproject_id UUID NOT NULL, \n\tstartgg_set_id VARCHAR(40) NOT NULL, \n\tplayed_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tstartgg_event_id VARCHAR(40) NOT NULL, \n\ttournament_name VARCHAR(300) NOT NULL, \n\ttournament_slug VARCHAR(300), \n\tevent_entrants INTEGER, \n\tonline BOOLEAN NOT NULL, \n\tcountry VARCHAR(8), \n\tp1_player_id VARCHAR(40), \n\tp1_tag VARCHAR(200), \n\tp1_placement INTEGER, \n\tp2_player_id VARCHAR(40), \n\tp2_tag VARCHAR(200), \n\tp2_placement INTEGER, \n\twinner_player_id VARCHAR(40), \n\tclassification VARCHAR(40) NOT NULL, \n\tcounted BOOLEAN NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_seeding_sets PRIMARY KEY (id), \n\tCONSTRAINT uq_seeding_sets_project_id_startgg_set_id UNIQUE (project_id, startgg_set_id), \n\tCONSTRAINT fk_seeding_sets_project_id_seeding_projects FOREIGN KEY(project_id) REFERENCES seeding_projects (id) ON DELETE CASCADE\n)"
    )
    op.execute("CREATE INDEX ix_seeding_sets_project_id ON seeding_sets (project_id)")
    op.execute(
        "CREATE TABLE seeding_results (\n\trun_id UUID NOT NULL, \n\tstartgg_player_id VARCHAR(40) NOT NULL, \n\tgamer_tag VARCHAR(120) NOT NULL, \n\tseed_algorithm INTEGER NOT NULL, \n\tmetrics JSON NOT NULL, \n\treasons JSON NOT NULL, \n\tflags JSON NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_seeding_results PRIMARY KEY (id), \n\tCONSTRAINT uq_seeding_results_run_id_startgg_player_id UNIQUE (run_id, startgg_player_id), \n\tCONSTRAINT uq_seeding_results_run_id_seed_algorithm UNIQUE (run_id, seed_algorithm), \n\tCONSTRAINT fk_seeding_results_run_id_seeding_runs FOREIGN KEY(run_id) REFERENCES seeding_runs (id) ON DELETE CASCADE\n)"
    )
    op.execute("CREATE INDEX ix_seeding_results_run_id ON seeding_results (run_id)")
    op.execute(
        "CREATE TABLE seeding_overrides (\n\tproject_id UUID NOT NULL, \n\tstartgg_player_id VARCHAR(40) NOT NULL, \n\tseed INTEGER NOT NULL, \n\treason VARCHAR(300) NOT NULL, \n\tactor VARCHAR(60) NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_seeding_overrides PRIMARY KEY (id), \n\tCONSTRAINT uq_seeding_overrides_project_id_startgg_player_id UNIQUE (project_id, startgg_player_id), \n\tCONSTRAINT ck_seeding_overrides_positive_seed CHECK (seed >= 1), \n\tCONSTRAINT fk_seeding_overrides_project_id_seeding_projects FOREIGN KEY(project_id) REFERENCES seeding_projects (id) ON DELETE CASCADE\n)"
    )
    op.execute("CREATE INDEX ix_seeding_overrides_project_id ON seeding_overrides (project_id)")
    op.execute(
        "CREATE TABLE seeding_audit_entries (\n\tproject_id UUID NOT NULL, \n\taction VARCHAR(40) NOT NULL, \n\tactor VARCHAR(60) NOT NULL, \n\tdetails JSON NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_seeding_audit_entries PRIMARY KEY (id), \n\tCONSTRAINT fk_seeding_audit_entries_project_id_seeding_projects FOREIGN KEY(project_id) REFERENCES seeding_projects (id) ON DELETE CASCADE\n)"
    )
    op.execute(
        "CREATE INDEX ix_seeding_audit_entries_project_id ON seeding_audit_entries (project_id)"
    )
    op.execute(
        "ALTER TABLE seeding_projects ADD CONSTRAINT fk_seeding_project_run FOREIGN KEY(current_run_id) REFERENCES seeding_runs (id)"
    )


def downgrade():
    op.execute("ALTER TABLE seeding_projects DROP CONSTRAINT fk_seeding_project_run")
    op.execute("DROP TABLE seeding_audit_entries")
    op.execute("DROP TABLE seeding_overrides")
    op.execute("DROP TABLE seeding_results")
    op.execute("DROP TABLE seeding_sets")
    op.execute("DROP TABLE seeding_entrants")
    op.execute("DROP TABLE seeding_runs")
    op.execute("DROP TABLE seeding_projects")
