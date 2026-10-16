from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.statistics import service
from app.statistics.contracts import (
    Filters,
    HeadToHeadView,
    ListingFilters,
    MatchPage,
    OpponentPage,
    PlacementPage,
    StatisticsView,
)

router = APIRouter(
    prefix="/api/v1/players",
    tags=["statistics"],
    responses={404: {"description": "Player not found or unpublished"}},
)


def execute(request, operation, *args):
    with Session(request.app.state.engine) as session:
        # Each response sees one committed snapshot, including all aggregates and
        # history pages, even if an import commits while it is being calculated.
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        try:
            return operation(session, *args)
        except service.PlayerNotFound:
            raise HTTPException(404, "Player not found") from None
        except service.SelfComparison:
            raise HTTPException(422, "A player cannot face themselves") from None


@router.get("/{id}/statistics", response_model=StatisticsView)
def statistics(request: Request, id: UUID, filters: Annotated[Filters, Query()]):
    return execute(request, service.statistics, id, filters)


@router.get("/{id}/matches", response_model=MatchPage)
def matches(request: Request, id: UUID, filters: Annotated[ListingFilters, Query()]):
    return execute(request, service.matches, id, filters)


@router.get("/{id}/opponents", response_model=OpponentPage)
def opponents(request: Request, id: UUID, filters: Annotated[ListingFilters, Query()]):
    return execute(request, service.opponents, id, filters)


@router.get("/{id}/placements", response_model=PlacementPage)
def placements(request: Request, id: UUID, filters: Annotated[ListingFilters, Query()]):
    return execute(request, service.placements, id, filters)


@router.get("/{id}/head-to-head/{opponent_id}", response_model=HeadToHeadView)
def head_to_head(
    request: Request, id: UUID, opponent_id: UUID, filters: Annotated[ListingFilters, Query()]
):
    return execute(request, service.head_to_head, id, opponent_id, filters)
