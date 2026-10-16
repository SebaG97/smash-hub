from alembic import context

from app.core.config import get_settings
from app.database import models  # noqa: F401
from app.database.base import Base
from app.database.session import build_engine

engine = build_engine(get_settings(), migration=True)
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        # Avoid concurrent deploy migrations. Release automatically on commit/rollback.
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(734291001)")
        context.run_migrations()
engine.dispose()
