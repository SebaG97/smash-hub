from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings


def build_engine(settings: Settings, *, migration: bool = False):
    secret = settings.migration_database_url if migration else settings.database_url
    if secret is None:
        raise ValueError("MIGRATION_DATABASE_URL must be explicitly configured")
    url = make_url(secret.get_secret_value()).set(drivername="postgresql+psycopg")
    args = {"connect_timeout": 3, "options": "-c statement_timeout=5000"}
    if settings.db_ca_cert:
        args["sslrootcert"] = settings.db_ca_cert
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=5,
        connect_args=args,
        hide_parameters=True,
    )


def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
