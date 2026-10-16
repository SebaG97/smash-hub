from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.competitions.router import router as competitions_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handling
from app.core.logging import configure_logging
from app.database.session import build_engine
from app.health.router import router


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
        yield
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
    install_error_handling(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )
    app.include_router(router)
    app.include_router(competitions_router)

    return app
