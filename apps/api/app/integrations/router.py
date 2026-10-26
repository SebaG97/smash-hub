"""Tournament imports from the web, protected by the admin key (Mission 06)."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.core.admin import Admin
from app.integrations.startgg import bulk
from app.integrations.startgg.client import ImportFailure

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

MESSAGES = {
    "startgg_token_missing": "La API no tiene STARTGG_API_TOKEN configurado.",
    "invalid_tournament_url": "Ese link no es de un torneo de start.gg.",
    "invalid_tournament_slug": "Ese link no es de un torneo de start.gg.",
}


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["country", "links"] = "country"
    country: str = Field(default="PY", pattern=r"^[A-Za-z]{2}$")
    window_start: AwareDatetime | None = None
    end: AwareDatetime | None = None
    urls: list[str] = Field(default_factory=list, max_length=50)


@router.post("/startgg", status_code=202)
def start_import(request: Request, body: ImportRequest, actor: Admin, response: Response):
    if body.source == "country" and (body.window_start is None or body.end is None):
        raise HTTPException(422, "Indica desde y hasta.")
    if body.source == "links" and not body.urls:
        raise HTTPException(422, "Pega al menos un link de torneo.")
    try:
        bulk.start(
            request.app.state.engine,
            request.app.state.settings.startgg_api_token,
            actor,
            country=body.country.upper() if body.source == "country" else None,
            start=body.window_start,
            end=body.end,
            urls=body.urls if body.source == "links" else None,
        )
    except bulk.ImportBusy:
        raise HTTPException(409, "Ya hay una importación en curso.") from None
    except ImportFailure as exc:
        raise HTTPException(422, MESSAGES.get(str(exc), "No se pudo iniciar.")) from None
    return {"status": "started"}


@router.get("/status")
def import_status(actor: Admin):
    return bulk.status()
