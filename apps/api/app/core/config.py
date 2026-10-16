from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


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
        if self.environment == "production":
            if not self.db_ca_cert or not all(o.startswith("https://") for o in self.cors_origins):
                raise ValueError("Production requires a CA path and HTTPS origins")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
