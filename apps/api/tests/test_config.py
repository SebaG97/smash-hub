import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "values",
    [
        {"database_url": "sqlite:///test.db"},
        {"cors_origins": ["*"]},
        {"db_pool_size": 50},
        {"environment": "production"},
    ],
)
def test_invalid_config(values):
    config = {"database_url": "postgresql://u:p@localhost/db", **values}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **config)


def test_production_tls():
    s = Settings(
        _env_file=None,
        environment="production",
        migration_database_url=None,
        database_url="postgresql://u:p@db.example/db?sslmode=verify-full",
        db_ca_cert="/app/ca.pem",
        cors_origins=["https://hub.example"],
    )
    assert "u:p" not in repr(s)
