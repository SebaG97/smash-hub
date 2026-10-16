from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(prefix="/api/v1", tags=["platform"])


class HealthResponse(BaseModel):
    status: str


class MetaResponse(BaseModel):
    name: str
    version: str
    api_version: str
    capabilities: list[str]


@router.get("/health/live", response_model=HealthResponse)
def live():
    return {"status": "alive"}


@router.get(
    "/health/ready", response_model=HealthResponse, responses={503: {"model": HealthResponse}}
)
def ready(request: Request):
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}


@router.get("/meta", response_model=MetaResponse)
def meta():
    return {
        "name": "Smash PY Hub",
        "version": "0.1.0",
        "api_version": "v1",
        "capabilities": ["health", "metadata"],
    }
