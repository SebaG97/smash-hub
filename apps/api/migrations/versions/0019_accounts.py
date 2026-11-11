"""Own accounts with roles and player links; retires the start.gg sign-in
(Mission SH-AUTH-01, ADR-021).

Accounts created by the start.gg sign-in keep their predictions and achievements: they get
the username "sgg-<start.gg user id>", no e-mail and no password (they cannot sign in),
and their verified start.gg player becomes a player link (method "startgg_legacy").
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

LEGACY_VERIFICATION = "Ingreso con start.gg (OAuth) anterior a la Misión SH-AUTH-01"


def upgrade():
    op.create_table(
        "auth_audit_entries",
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_auth_audit_entries_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            name=op.f("fk_auth_audit_entries_target_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_audit_entries")),
    )
    op.create_index(
        op.f("ix_auth_audit_entries_action"), "auth_audit_entries", ["action"], unique=False
    )
    op.create_index(
        op.f("ix_auth_audit_entries_actor_id"), "auth_audit_entries", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_auth_audit_entries_target_user_id"),
        "auth_audit_entries",
        ["target_user_id"],
        unique=False,
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["issued_by"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_issued_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False
    )
    op.create_table(
        "player_link_requests",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("evidence", sa.String(length=1000), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_name", sa.String(length=80), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name=op.f("ck_player_link_requests_status"),
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], name=op.f("fk_player_link_requests_player_id_players")
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name=op.f("fk_player_link_requests_reviewed_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_player_link_requests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_player_link_requests")),
    )
    op.create_index(
        op.f("ix_player_link_requests_player_id"),
        "player_link_requests",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_link_requests_user_id"), "player_link_requests", ["user_id"], unique=False
    )
    op.create_index(
        "uq_player_link_requests_pending_user",
        "player_link_requests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "player_links",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("verification", sa.String(length=500), nullable=False),
        sa.Column("linked_by", sa.Uuid(), nullable=True),
        sa.Column("linked_by_name", sa.String(length=80), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_by", sa.Uuid(), nullable=True),
        sa.Column("unlinked_by_name", sa.String(length=80), nullable=True),
        sa.Column("unlink_reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('request', 'admin', 'startgg_legacy')", name=op.f("ck_player_links_method")
        ),
        sa.ForeignKeyConstraint(
            ["linked_by"],
            ["users.id"],
            name=op.f("fk_player_links_linked_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["players.id"], name=op.f("fk_player_links_player_id_players")
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["player_link_requests.id"],
            name=op.f("fk_player_links_request_id_player_link_requests"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["unlinked_by"],
            ["users.id"],
            name=op.f("fk_player_links_unlinked_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_player_links_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_player_links")),
    )
    op.create_index(op.f("ix_player_links_player_id"), "player_links", ["player_id"], unique=False)
    op.create_index(op.f("ix_player_links_user_id"), "player_links", ["user_id"], unique=False)
    op.create_index(
        "uq_player_links_active_player",
        "player_links",
        ["player_id"],
        unique=True,
        postgresql_where=sa.text("unlinked_at IS NULL"),
    )
    op.create_index(
        "uq_player_links_active_user",
        "player_links",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("unlinked_at IS NULL"),
    )
    # Users: new columns nullable first, filled, then constrained.
    op.alter_column("users", "banned_at", new_column_name="disabled_at")
    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(length=254), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column(
        "users", sa.Column("role", sa.String(length=20), server_default="user", nullable=False)
    )
    op.add_column(
        "users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE users SET username = left('sgg-' || lower(regexp_replace("
        "provider_user_id, '[^a-zA-Z0-9_.-]', '', 'g')), 30)"
    )
    # A verified start.gg player becomes a link when the hub knows that player. If two
    # accounts point at one hub player (or the reverse), only the oldest pair is linked.
    op.execute(
        f"""
        INSERT INTO player_links
            (id, user_id, player_id, method, verification, linked_by_name, created_at, updated_at)
        SELECT gen_random_uuid(), user_id, player_id, 'startgg_legacy',
               '{LEGACY_VERIFICATION}', 'sistema', now(), now()
        FROM (
            SELECT u.id AS user_id, ei.player_id,
                   row_number() OVER (PARTITION BY ei.player_id ORDER BY u.created_at, u.id) AS rp,
                   row_number() OVER (PARTITION BY u.id ORDER BY ei.created_at, ei.id) AS ru
            FROM users u
            JOIN external_identities ei ON ei.external_id = 'player:' || u.startgg_player_id
            WHERE u.startgg_player_id IS NOT NULL
        ) pairs
        WHERE rp = 1 AND ru = 1
        """
    )
    op.alter_column("users", "username", nullable=False)
    op.drop_index(op.f("ix_users_startgg_player_id"), table_name="users")
    op.drop_constraint(op.f("uq_users_provider_provider_user_id"), "users", type_="unique")
    op.create_unique_constraint(op.f("uq_users_email"), "users", ["email"])
    op.create_unique_constraint(op.f("uq_users_username"), "users", ["username"])
    op.create_check_constraint(
        op.f("ck_users_role"), "users", "role IN ('user', 'admin', 'superadmin')"
    )
    op.create_check_constraint(
        op.f("ck_users_username_format"), "users", "username ~ '^[a-z0-9_.-]{3,30}$'"
    )
    op.drop_column("users", "provider")
    op.drop_column("users", "provider_user_id")
    op.drop_column("users", "startgg_player_id")
    op.drop_column("users", "slug")


def downgrade():
    """Back to 0018. Local accounts become provider 'local' (0018 cannot sign them in);
    passwords, roles, links, requests, reset tokens and the audit log are dropped."""
    op.add_column("users", sa.Column("provider", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("provider_user_id", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("slug", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("startgg_player_id", sa.String(length=20), nullable=True))
    op.execute(
        "UPDATE users SET provider = 'startgg', provider_user_id = substr(username, 5) "
        "WHERE username LIKE 'sgg-%' AND password_hash IS NULL"
    )
    op.execute(
        "UPDATE users SET provider = 'local', provider_user_id = id::text WHERE provider IS NULL"
    )
    op.execute(
        """
        UPDATE users u SET startgg_player_id = substr(ei.external_id, 8)
        FROM player_links pl
        JOIN external_identities ei
          ON ei.player_id = pl.player_id AND ei.external_id LIKE 'player:%'
        WHERE pl.user_id = u.id AND pl.unlinked_at IS NULL
          AND length(ei.external_id) <= 27
        """
    )
    op.alter_column("users", "provider", nullable=False)
    op.alter_column("users", "provider_user_id", nullable=False)
    op.drop_constraint(op.f("ck_users_username_format"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.drop_constraint(op.f("uq_users_username"), "users", type_="unique")
    op.drop_constraint(op.f("uq_users_email"), "users", type_="unique")
    op.create_unique_constraint(
        op.f("uq_users_provider_provider_user_id"), "users", ["provider", "provider_user_id"]
    )
    op.create_index(
        op.f("ix_users_startgg_player_id"), "users", ["startgg_player_id"], unique=False
    )
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
    op.drop_column("users", "username")
    op.alter_column("users", "disabled_at", new_column_name="banned_at")
    op.drop_index(
        "uq_player_links_active_user",
        table_name="player_links",
        postgresql_where=sa.text("unlinked_at IS NULL"),
    )
    op.drop_index(
        "uq_player_links_active_player",
        table_name="player_links",
        postgresql_where=sa.text("unlinked_at IS NULL"),
    )
    op.drop_index(op.f("ix_player_links_user_id"), table_name="player_links")
    op.drop_index(op.f("ix_player_links_player_id"), table_name="player_links")
    op.drop_table("player_links")
    op.drop_index(
        "uq_player_link_requests_pending_user",
        table_name="player_link_requests",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index(op.f("ix_player_link_requests_user_id"), table_name="player_link_requests")
    op.drop_index(op.f("ix_player_link_requests_player_id"), table_name="player_link_requests")
    op.drop_table("player_link_requests")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index(op.f("ix_auth_audit_entries_target_user_id"), table_name="auth_audit_entries")
    op.drop_index(op.f("ix_auth_audit_entries_actor_id"), table_name="auth_audit_entries")
    op.drop_index(op.f("ix_auth_audit_entries_action"), table_name="auth_audit_entries")
    op.drop_table("auth_audit_entries")
