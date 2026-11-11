from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# The legacy admin key cannot be extended further than this at a time (ADR-021).
LEGACY_ADMIN_MAX_DAYS = 90


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    migration_database_url: SecretStr | None = None
    cors_origins: list[str] = ["http://localhost:3000"]
    db_pool_size: int = Field(default=3, ge=1, le=10)
    db_max_overflow: int = Field(default=2, ge=0, le=5)
    db_ca_cert: str | None = None
    startgg_api_token: SecretStr | None = None
    # Uploading a seeding to start.gg (the hub's only write there) stays off unless set.
    startgg_seeding_writes: bool = False
    # Legacy shared admin key (ADR-011), kept only during the move to personal accounts
    # (ADR-021). It works only while ADMIN_TOKEN_EXPIRES is set and in the future.
    admin_token: SecretStr | None = None
    admin_token_expires: datetime | None = None
    # Header where the trusted proxy puts the visitor's address (App Platform:
    # do-connecting-ip). Unset: only the socket peer is used, no header is trusted.
    client_ip_header: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,64}$")

    @model_validator(mode="after")
    def validate_security(self):
        for secret in [self.database_url, self.migration_database_url]:
            if secret is None:
                continue
            try:
                url = make_url(secret.get_secret_value())
                valid = url.drivername in ("postgresql", "postgresql+psycopg")
            except Exception:
                valid = False
            if not valid:
                raise ValueError("A valid PostgreSQL URL is required")
            if self.environment == "production" and url.query.get("sslmode") != "verify-full":
                raise ValueError("Production PostgreSQL requires sslmode=verify-full and a CA")
        if any(o == "*" or not o.startswith(("http://", "https://")) for o in self.cors_origins):
            raise ValueError("CORS requires explicit HTTP origins")
        if self.admin_token is not None and len(self.admin_token.get_secret_value()) < 24:
            raise ValueError("ADMIN_TOKEN must have at least 24 characters")
        expires = self.admin_token_expires
        if expires is not None:
            if expires.tzinfo is None:
                raise ValueError("ADMIN_TOKEN_EXPIRES needs a time zone, e.g. 2026-12-31T23:59Z")
            if expires > datetime.now(UTC) + timedelta(days=LEGACY_ADMIN_MAX_DAYS):
                raise ValueError(
                    f"ADMIN_TOKEN_EXPIRES can be at most {LEGACY_ADMIN_MAX_DAYS} days ahead"
                )
        if self.environment == "production":
            if not self.db_ca_cert or not all(o.startswith("https://") for o in self.cors_origins):
                raise ValueError("Production requires a CA path and HTTPS origins")
        return self

    def legacy_admin_active(self, now=None):
        """The shared key still opens admin routes: set, dated and not yet expired."""
        return (
            self.admin_token is not None
            and self.admin_token_expires is not None
            and (now or datetime.now(UTC)) < self.admin_token_expires
        )

    def web_origin(self):
        """The web's origin: the first CORS origin (same site in production)."""
        return self.cors_origins[0].rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
