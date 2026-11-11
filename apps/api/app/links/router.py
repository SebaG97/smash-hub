"""A signed-in person asking to be linked to their player record (ADR-021)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.service import AuthError, Member
from app.links import service

router = APIRouter(prefix="/api/v1/links", tags=["links"])


class LinkRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: UUID
    evidence: str = Field(min_length=1, max_length=1000)


def _session(request):
    return Session(request.app.state.engine, expire_on_commit=False)


def _fail(exc: AuthError):
    raise HTTPException(exc.status, str(exc)) from None


def _mine(s, user):
    return dict(
        player=service.active_player(s, user.id),
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
