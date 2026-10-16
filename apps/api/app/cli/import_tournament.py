"""Administrative CLI; no HTTP write route and no credential output."""

import argparse
import asyncio
import json

from pydantic import ValidationError

from app.core.config import get_settings
from app.database import models  # noqa: F401
from app.database.session import build_engine
from app.integrations.startgg.client import ImportFailure, StartGGClient, parse_slug
from app.integrations.startgg.service import run_import


async def execute(args):
    slug = parse_slug(args.slug)
    settings = get_settings()
    if settings.environment == "production":
        raise ImportFailure("production_import_disabled_this_mission")
    async with StartGGClient(settings.startgg_api_token) as client:
        engine = (
            None
            if args.dry_run
            else build_engine(settings.model_copy(update={"db_pool_size": 1, "db_max_overflow": 0}))
        )
        try:
            return await run_import(
                engine, client, slug, community_slug=args.community, dry_run=args.dry_run
            )
        finally:
            if engine is not None:
                engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Importar un torneo start.gg; publicación atómica")
    parser.add_argument("--slug", required=True, help="Slug o URL HTTPS oficial del torneo")
    parser.add_argument("--community", default="smash-paraguay")
    parser.add_argument(
        "--dry-run", action="store_true", help="Descargar y validar sin escribir en PostgreSQL"
    )
    args = parser.parse_args()
    try:
        result = asyncio.run(execute(args))
    except ImportFailure as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1
    except ValidationError:
        print('{"status":"failed","error":"invalid_configuration"}')
        return 2
    except Exception:
        print('{"status":"failed","error":"import_unavailable"}')
        return 1
    print(
        json.dumps(
            {"status": "validated" if args.dry_run else "completed", **result}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
