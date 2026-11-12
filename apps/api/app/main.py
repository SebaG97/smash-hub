from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.achievements import runner as achievements_runner
from app.achievements.router import router as achievements_router
from app.auth.admin_router import router as accounts_admin_router
from app.auth.router import router as auth_router
from app.brackets.router import router as brackets_router
from app.competitions.router import router as competitions_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handling
from app.core.logging import configure_logging
from app.database.session import build_engine
from app.health.router import router
from app.insights.router import router as insights_router
from app.integrations.router import router as imports_router
from app.links.router import router as links_router
from app.live.router import router as live_router
from app.prode.router import router as prode_router
from app.seeding.router import router as seeding_router
from app.statistics.router import router as statistics_router
from app.sync.router import router as sync_router
from app.sync.scheduler import maybe_start
from app.teams.router import router as teams_router


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    if settings is None:
        try:
            settings = get_settings()
        except ValidationError:
            raise RuntimeError(
                "Invalid configuration; check required variables and TLS/CORS"
            ) from None
    configure_logging()

    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = engine if engine is not None else build_engine(settings)
        # Background start.gg sync (ADR-022): only with STARTGG_SYNC_ENABLED and a token.
        scheduler = maybe_start(app.state.engine, settings)
        # Background achievements (SH-ACH-01): only with ACHIEVEMENTS_AUTO.
        achievements = achievements_runner.maybe_start(app.state.engine, settings)
        yield
        if scheduler is not None:
            scheduler.stop()
        if achievements is not None:
            achievements.stop()
        if engine is None:
            app.state.engine.dispose()

    app = FastAPI(
        title="Smash PY Hub API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    install_error_handling(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Writes with the session cookie need X-Requested-With, which only these origins
        # may send (ADR-021). Authorization/X-Admin-Name: legacy shared key, transition only.
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "Authorization",
            "X-Admin-Name",
            "X-Requested-With",
        ],
    )
    app.include_router(router)
    app.include_router(competitions_router)
    app.include_router(statistics_router)
    app.include_router(seeding_router)
    app.include_router(imports_router)
    app.include_router(insights_router)
    app.include_router(teams_router)
    app.include_router(brackets_router)
    app.include_router(live_router)
    app.include_router(auth_router)
    app.include_router(prode_router)
    app.include_router(links_router)
    app.include_router(accounts_admin_router)
    app.include_router(sync_router)
    app.include_router(achievements_router)

    return app
