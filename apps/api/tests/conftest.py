import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def pg_engine():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL absent; use isolated Compose tests for PostgreSQL")
    parsed = make_url(url)
    # Deliberate guard: these destructive tests only accept the dedicated test database.
    if parsed.database != "smashhub_test" or parsed.host not in {
        "localhost",
        "127.0.0.1",
        "postgres",
    }:
        pytest.fail("Refusing a non-local or non-test database")
    os.environ["DATABASE_URL"] = url
    os.environ["MIGRATION_DATABASE_URL"] = url
    os.environ["ENVIRONMENT"] = "test"
    from app.core.config import get_settings

    get_settings.cache_clear()
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")
    engine = create_engine(parsed.set(drivername="postgresql+psycopg"))
    yield engine
    # Imported fixtures may contain results that 0001 cannot represent.
    # Remove only data in the guarded, disposable test database before teardown.
    from app.database.base import Base

    with engine.begin() as conn:
        names = ",".join('"' + name + '"' for name in Base.metadata.tables)
        conn.execute(text("TRUNCATE " + names + " CASCADE"))
    engine.dispose()
    command.downgrade(cfg, "base")
    get_settings.cache_clear()


@pytest.fixture
def db(pg_engine):
    from app.database import models  # noqa: F401
    from app.database.base import Base

    with pg_engine.begin() as conn:
        names = ",".join('"' + name + '"' for name in Base.metadata.tables)
        conn.execute(text("TRUNCATE " + names + " CASCADE"))
    return pg_engine


@pytest.fixture(autouse=True)
def fresh_admin_limiter():
    """Each test starts without failed admin attempts from earlier tests."""
    from app.core import admin

    admin._failures.clear()
    yield
    admin._failures.clear()
