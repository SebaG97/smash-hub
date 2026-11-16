"""A signed-in person asking to be linked to their player record (ADR-021)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.service import AuthError, Member
from app.links import service
from app.players.mains import UnknownCharacter, player_mains, set_costume
from app.players.models import Player

router = APIRouter(prefix="/api/v1/links", tags=["links"])


class LinkRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: UUID
    evidence: str = Field(min_length=1, max_length=1000)


def _session(request):
    return Session(request.app.state.engine, expire_on_commit=False)


def _fail(exc: AuthError):
    raise HTTPException(exc.status, str(exc)) from None


class CostumeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    character: str = Field(min_length=1, max_length=120)
    costume: int = Field(ge=1, le=8)


def _mine(s, user):
    player = service.active_player(s, user.id)
    if player:
        # Their mains with the costume share images use, to choose it themselves.
        player["mains"] = player_mains(s, [UUID(player["id"])]).get(UUID(player["id"]), [])
    return dict(
        player=player,
        requests=service.describe_requests(s, service.requests_of(s, user)),
    )


@router.get("/players")
def players(request: Request, user: Member, q: Annotated[str, Query(max_length=60)] = ""):
    """Player records to ask for, by tag."""
    with _session(request) as s:
        return service.search_players(s, q)


@router.get("/mine")
def mine(request: Request, user: Member):
    with _session(request) as s:
        return _mine(s, user)


@router.put("/mine/costume")
def set_my_costume(request: Request, body: CostumeBody, user: Member):
    """The linked player chooses the costume share images show for one of their mains.
    Organizers can still change it; the last choice stays."""
    with _session(request) as s:
        with s.begin():
            player_id = service.linked_player_id(s, user.id)
            if player_id is None:
                raise HTTPException(409, "Tu cuenta no está vinculada a una ficha de jugador.")
            try:
                set_costume(s, s.get(Player, player_id), body.character, body.costume)
            except UnknownCharacter:
                raise HTTPException(422, "No existe ese personaje.") from None
        return _mine(s, user)


@router.post("/requests", status_code=201)
def create_request(request: Request, body: LinkRequestBody, user: Member):
    with _session(request) as s:
        try:
            with s.begin():
                service.create_request(s, user, body.player_id, body.evidence)
        except AuthError as exc:
            _fail(exc)
        return _mine(s, user)


@router.delete("/requests/{request_id}")
def cancel_request(request: Request, request_id: UUID, user: Member):
    with _session(request) as s:
        try:
            with s.begin():
                service.cancel_request(s, user, request_id)
        except AuthError as exc:
            _fail(exc)
        return _mine(s, user)
