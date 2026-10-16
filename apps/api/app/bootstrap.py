import argparse

from app.communities.service import bootstrap
from app.core.config import get_settings
from app.database import models  # noqa: F401
from app.database.session import build_engine, session_factory


def main():
    parser = argparse.ArgumentParser(description="Explicit, idempotent reference-data bootstrap")
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment == "production" and not args.allow_production:
        parser.error("Production bootstrap requires explicit --allow-production")
    engine = build_engine(settings)
    try:
        with session_factory(engine).begin() as session:
            bootstrap(session)
        print("Bootstrap complete: PY, Smash Paraguay, SSBU, start.gg")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
