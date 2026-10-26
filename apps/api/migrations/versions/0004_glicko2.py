"""Immutable rating policies, versioned calculation runs and snapshots."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TABLE rating_policies (\n\tversion VARCHAR(80) NOT NULL, \n\tparameters JSON NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_rating_policies PRIMARY KEY (id), \n\tCONSTRAINT uq_rating_policies_version UNIQUE (version)\n)"
    )
    op.execute(
        "CREATE TABLE rating_pools (\n\tslug VARCHAR(120) NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tgame_id UUID NOT NULL, \n\tcommunity_id UUID NOT NULL, \n\tpolicy_id UUID NOT NULL, \n\tmode VARCHAR(20) NOT NULL, \n\tevent_ids JSON NOT NULL, \n\tplayer_ids JSON, \n\tpublished_run_id UUID, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_rating_pools PRIMARY KEY (id), \n\tCONSTRAINT ck_rating_pools_pool_mode CHECK (mode IN ('singles','doubles')), \n\tCONSTRAINT uq_rating_pools_slug UNIQUE (slug), \n\tCONSTRAINT fk_rating_pools_game_id_games FOREIGN KEY(game_id) REFERENCES games (id), \n\tCONSTRAINT fk_rating_pools_community_id_communities FOREIGN KEY(community_id) REFERENCES communities (id), \n\tCONSTRAINT fk_rating_pools_policy_id_rating_policies FOREIGN KEY(policy_id) REFERENCES rating_policies (id)\n)"
    )
    op.execute("CREATE INDEX ix_rating_pools_community_id ON rating_pools (community_id)")
    op.execute("CREATE INDEX ix_rating_pools_game_id ON rating_pools (game_id)")
    op.execute(
        "CREATE TABLE rating_calculation_runs (\n\tpool_id UUID NOT NULL, \n\tpolicy_id UUID NOT NULL, \n\tpolicy_version VARCHAR(80) NOT NULL, \n\talgorithm_version VARCHAR(80) NOT NULL, \n\tparameters JSON NOT NULL, \n\tinput_hash VARCHAR(64), \n\tstatus VARCHAR(20) NOT NULL, \n\tinterval_start TIMESTAMP WITH TIME ZONE, \n\tinterval_end TIMESTAMP WITH TIME ZONE NOT NULL, \n\trequested_from TIMESTAMP WITH TIME ZONE, \n\tstarted_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tfinished_at TIMESTAMP WITH TIME ZONE, \n\tplayer_count INTEGER NOT NULL, \n\tset_count INTEGER NOT NULL, \n\texcluded_undated INTEGER NOT NULL, \n\terror VARCHAR(200), \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_rating_calculation_runs PRIMARY KEY (id), \n\tCONSTRAINT uq_rating_calculation_runs_pool_id_input_hash UNIQUE (pool_id, input_hash), \n\tCONSTRAINT uq_rating_calculation_runs_id_pool_id UNIQUE (id, pool_id), \n\tCONSTRAINT ck_rating_calculation_runs_run_status CHECK (status IN ('RUNNING','COMPLETED','FAILED')), \n\tCONSTRAINT fk_rating_calculation_runs_pool_id_rating_pools FOREIGN KEY(pool_id) REFERENCES rating_pools (id), \n\tCONSTRAINT fk_rating_calculation_runs_policy_id_rating_policies FOREIGN KEY(policy_id) REFERENCES rating_policies (id)\n)"
    )
    op.execute(
        "CREATE INDEX ix_rating_calculation_runs_pool_id ON rating_calculation_runs (pool_id)"
    )
    op.execute(
        "CREATE TABLE rating_periods (\n\tpool_id UUID NOT NULL, \n\tstarts_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tends_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_rating_periods PRIMARY KEY (id), \n\tCONSTRAINT uq_rating_periods_pool_id_starts_at_ends_at UNIQUE (pool_id, starts_at, ends_at), \n\tCONSTRAINT uq_rating_periods_id_pool_id UNIQUE (id, pool_id), \n\tCONSTRAINT ck_rating_periods_period_bounds CHECK (ends_at > starts_at), \n\tCONSTRAINT fk_rating_periods_pool_id_rating_pools FOREIGN KEY(pool_id) REFERENCES rating_pools (id)\n)"
    )
    op.execute("CREATE INDEX ix_rating_periods_pool_id ON rating_periods (pool_id)")
    op.execute(
        "CREATE TABLE rating_snapshots (\n\trun_id UUID NOT NULL, \n\tpool_id UUID NOT NULL, \n\tperiod_id UUID NOT NULL, \n\tplayer_id UUID NOT NULL, \n\trating FLOAT NOT NULL, \n\trd FLOAT NOT NULL, \n\tvolatility FLOAT NOT NULL, \n\tperiod_sets INTEGER NOT NULL, \n\tcumulative_sets INTEGER NOT NULL, \n\tlast_activity TIMESTAMP WITH TIME ZONE, \n\tcalculated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tpolicy_version VARCHAR(80) NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_rating_snapshots PRIMARY KEY (id), \n\tCONSTRAINT fk_rating_snapshots_run_id_rating_calculation_runs FOREIGN KEY(run_id, pool_id) REFERENCES rating_calculation_runs (id, pool_id), \n\tCONSTRAINT fk_rating_snapshots_period_id_rating_periods FOREIGN KEY(period_id, pool_id) REFERENCES rating_periods (id, pool_id), \n\tCONSTRAINT uq_rating_snapshots_run_id_period_id_player_id UNIQUE (run_id, period_id, player_id), \n\tCONSTRAINT uq_rating_snapshots_id_run_id_pool_id_period_id UNIQUE (id, run_id, pool_id, period_id), \n\tCONSTRAINT ck_rating_snapshots_finite_rating CHECK (rd > 0 AND rd < 'Infinity'::float8 AND volatility > 0 AND volatility < 'Infinity'::float8 AND rating > '-Infinity'::float8 AND rating < 'Infinity'::float8), \n\tCONSTRAINT ck_rating_snapshots_snapshot_counts CHECK (period_sets >= 0 AND cumulative_sets >= period_sets), \n\tCONSTRAINT fk_rating_snapshots_player_id_players FOREIGN KEY(player_id) REFERENCES players (id)\n)"
    )
    op.execute("CREATE INDEX ix_rating_snapshots_period_id ON rating_snapshots (period_id)")
    op.execute("CREATE INDEX ix_rating_snapshots_player_id ON rating_snapshots (player_id)")
    op.execute("CREATE INDEX ix_rating_snapshots_pool_id ON rating_snapshots (pool_id)")
    op.execute("CREATE INDEX ix_rating_snapshots_run_id ON rating_snapshots (run_id)")
    op.execute(
        "CREATE TABLE ranking_snapshots (\n\trating_snapshot_id UUID NOT NULL, \n\trun_id UUID NOT NULL, \n\tpool_id UUID NOT NULL, \n\tperiod_id UUID NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tposition INTEGER NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tCONSTRAINT pk_ranking_snapshots PRIMARY KEY (id), \n\tCONSTRAINT fk_ranking_snapshots_rating_snapshot_id_rating_snapshots FOREIGN KEY(rating_snapshot_id, run_id, pool_id, period_id) REFERENCES rating_snapshots (id, run_id, pool_id, period_id), \n\tCONSTRAINT uq_ranking_snapshots_run_id_period_id_status_position UNIQUE (run_id, period_id, status, position), \n\tCONSTRAINT ck_ranking_snapshots_ranking_status CHECK (status IN ('ACTIVE','PROVISIONAL','INACTIVE')), \n\tCONSTRAINT ck_ranking_snapshots_ranking_position CHECK (position > 0), \n\tCONSTRAINT uq_ranking_snapshots_rating_snapshot_id UNIQUE (rating_snapshot_id)\n)"
    )
    op.execute("CREATE INDEX ix_ranking_snapshots_period_id ON ranking_snapshots (period_id)")
    op.execute("CREATE INDEX ix_ranking_snapshots_pool_id ON ranking_snapshots (pool_id)")
    op.execute("CREATE INDEX ix_ranking_snapshots_run_id ON ranking_snapshots (run_id)")
    op.execute(
        "ALTER TABLE rating_pools ADD CONSTRAINT fk_pool_published_run FOREIGN KEY(published_run_id) REFERENCES rating_calculation_runs (id)"
    )


def downgrade():
    op.execute("ALTER TABLE rating_pools DROP CONSTRAINT fk_pool_published_run")
    op.drop_table("ranking_snapshots")
    op.drop_table("rating_snapshots")
    op.drop_table("rating_periods")
    op.drop_table("rating_calculation_runs")
    op.drop_table("rating_pools")
    op.drop_table("rating_policies")
