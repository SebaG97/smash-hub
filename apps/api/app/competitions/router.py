"""Public read models. No provider IDs, job internals, or source payloads."""

from datetime import datetime
from typing import Literal, TypeVar
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.competitions.models import (
    EntrantMember,
    Event,
    EventEntrant,
    Set,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.games.models import Game
from app.players.models import Player, PlayerAlias

router = APIRouter(
    prefix="/api/v1",
    tags=["competitions"],
    responses={404: {"description": "Record not found or unpublished"}},
)
T = TypeVar("T")


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class PublicModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class TournamentView(PublicModel):
    name: str
    slug: str
    starts_at: datetime | None
    ends_at: datetime | None
    status: str | None
    location: dict | None
    synced_at: datetime | None
    source: str | None
    participant_count: int
    entrant_count: int
    games: list[str]


class EventView(PublicModel):
    tournament_id: UUID
    name: str
    game: str
    team_size: int
    competition_type: int | None
    status: str | None
    entrant_count: int


class MemberView(BaseModel):
    player_id: UUID
    tag: str


class EntrantView(PublicModel):
    name: str
    seed: int | None
    placement: int | None
    members: list[MemberView]


class SideView(BaseModel):
    entrant_id: UUID | None
    name: str | None
    score: int | None
    is_winner: bool


class SetView(PublicModel):
    status: Literal["pending", "in_progress", "completed", "not_played", "unknown"]
    resolution: Literal["unresolved", "played", "dq", "bye", "placeholder", "conditional_unused"]
    classification_reason: str
    source_state: int | None
    stats_eligible: bool
    ranking_eligible: bool
    round_number: int | None
    round_label: str | None
    completed_at: datetime | None
    sides: list[SideView]


class PlayerView(PublicModel):
    tag: str


class ParticipationView(BaseModel):
    tournament_id: UUID
    tournament_name: str
    event_id: UUID
    event_name: str
    tag: str
    entrant_name: str
    placement: int | None


class PlayerDetail(PlayerView):
    aliases: list[str]
    history: Page[ParticipationView]
    scopes: list["PlayerScope"]


class PlayerScope(BaseModel):
    game_id: UUID
    game_name: str
    mode: Literal["singles", "doubles"]


def paginate(s, stmt, page, page_size):
    total = s.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return s.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all(), total


def page_result(items, total, page, page_size):
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def require_tournament(s, id):
    row = s.scalar(select(Tournament).where(Tournament.id == id, Tournament.published.is_(True)))
    if not row:
        raise HTTPException(404, "Tournament not found")
    return row


def require_event(s, id):
    row = s.scalar(
        select(Event).join(Tournament).where(Event.id == id, Tournament.published.is_(True))
    )
    if not row:
        raise HTTPException(404, "Event not found")
    return row


def tournament_views(s, rows):
    from app.integrations.models import DataSource, ExternalMapping

    ids = [r.id for r in rows]
    participants = dict(
        s.execute(
            select(TournamentParticipant.tournament_id, func.count())
            .where(TournamentParticipant.tournament_id.in_(ids))
            .group_by(TournamentParticipant.tournament_id)
        ).all()
    )
    entrants = dict(
        s.execute(
            select(EventEntrant.tournament_id, func.count())
            .where(EventEntrant.tournament_id.in_(ids))
            .group_by(EventEntrant.tournament_id)
        ).all()
    )
    games = {}
    for tid, name in s.execute(
        select(Event.tournament_id, Game.name)
        .join(Game)
        .where(Event.tournament_id.in_(ids))
        .distinct()
        .order_by(Game.name)
    ):
        games.setdefault(tid, []).append(name)
    sources = dict(
        s.execute(
            select(ExternalMapping.tournament_id, DataSource.name)
            .join(DataSource)
            .where(ExternalMapping.tournament_id.in_(ids))
        ).all()
    )
    return [
        {
            **{
                key: getattr(r, key)
                for key in (
                    "id",
                    "name",
                    "slug",
                    "starts_at",
                    "ends_at",
                    "status",
                    "location",
                    "synced_at",
                )
            },
            "participant_count": participants.get(r.id, 0),
            "entrant_count": entrants.get(r.id, 0),
            "games": games.get(r.id, []),
            "source": sources.get(r.id),
        }
        for r in rows
    ]


def event_views(s, rows):
    games = dict(
        s.execute(select(Game.id, Game.name).where(Game.id.in_([r.game_id for r in rows]))).all()
    )
    counts = dict(
        s.execute(
            select(EventEntrant.event_id, func.count())
            .where(EventEntrant.event_id.in_([r.id for r in rows]))
            .group_by(EventEntrant.event_id)
        ).all()
    )
    return [
        {
            **{
                key: getattr(r, key)
                for key in (
                    "id",
                    "tournament_id",
                    "name",
                    "team_size",
                    "competition_type",
                    "status",
                )
            },
            "game": games[r.game_id],
            "entrant_count": counts.get(r.id, 0),
        }
        for r in rows
    ]


@router.get("/tournaments", response_model=Page[TournamentView])
def tournaments(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=120),
    status: str | None = None,
    game_id: UUID | None = None,
):
    with Session(request.app.state.engine) as s:
        stmt = select(Tournament).where(Tournament.published.is_(True))
        if q:
            stmt = stmt.where(Tournament.name.icontains(q, autoescape=True))
        if status:
            stmt = stmt.where(Tournament.status == status)
        if game_id:
            stmt = stmt.where(
                select(Event.id)
                .where(Event.tournament_id == Tournament.id, Event.game_id == game_id)
                .exists()
            )
        rows, total = paginate(
            s,
            stmt.order_by(Tournament.starts_at.desc().nullslast(), Tournament.id),
            page,
            page_size,
        )
        return page_result(tournament_views(s, rows), total, page, page_size)


@router.get("/tournaments/{id}", response_model=TournamentView)
def tournament(request: Request, id: UUID):
    with Session(request.app.state.engine) as s:
        return tournament_views(s, [require_tournament(s, id)])[0]


@router.get("/tournaments/{id}/events", response_model=Page[EventView])
def events(
    request: Request,
    id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    game_id: UUID | None = None,
):
    with Session(request.app.state.engine) as s:
        require_tournament(s, id)
        stmt = select(Event).where(Event.tournament_id == id)
        if game_id:
            stmt = stmt.where(Event.game_id == game_id)
        rows, total = paginate(s, stmt.order_by(Event.name, Event.id), page, page_size)
        return page_result(event_views(s, rows), total, page, page_size)


@router.get("/events/{id}", response_model=EventView)
def event(request: Request, id: UUID):
    with Session(request.app.state.engine) as s:
        return event_views(s, [require_event(s, id)])[0]


@router.get("/events/{id}/entrants", response_model=Page[EntrantView])
def entrants(
    request: Request,
    id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=120),
):
    with Session(request.app.state.engine) as s:
        require_event(s, id)
        stmt = select(EventEntrant).where(EventEntrant.event_id == id)
        if q:
            stmt = stmt.where(EventEntrant.name.icontains(q, autoescape=True))
        rows, total = paginate(
            s,
            stmt.order_by(
                EventEntrant.placement.asc().nullslast(),
                EventEntrant.seed.asc().nullslast(),
                EventEntrant.id,
            ),
            page,
            page_size,
        )
        members = {}
        for entrant_id, player_id, tag in s.execute(
            select(
                EntrantMember.entrant_id,
                TournamentParticipant.player_id,
                TournamentParticipant.tag_snapshot,
            )
            .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
            .where(EntrantMember.entrant_id.in_([r.id for r in rows]))
            .order_by(EntrantMember.position)
        ):
            members.setdefault(entrant_id, []).append({"player_id": player_id, "tag": tag})
        return page_result(
            [
                {
                    **{k: getattr(r, k) for k in ("id", "name", "seed", "placement")},
                    "members": members.get(r.id, []),
                }
                for r in rows
            ],
            total,
            page,
            page_size,
        )


@router.get("/events/{id}/sets", response_model=Page[SetView])
def sets(
    request: Request,
    id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Literal["pending", "in_progress", "completed", "not_played", "unknown"] | None = None,
    resolution: Literal["unresolved", "played", "dq", "bye", "placeholder", "conditional_unused"]
    | None = None,
    view: Literal["matches", "bracket", "all"] = "matches",
):
    with Session(request.app.state.engine) as s:
        require_event(s, id)
        stmt = select(Set).where(Set.event_id == id)
        if status:
            stmt = stmt.where(Set.lifecycle_status == status)
        if resolution:
            stmt = stmt.where(Set.resolution == resolution)
        bracket = Set.resolution.in_(["placeholder", "conditional_unused"])
        if view == "matches":
            stmt = stmt.where(~bracket)
        elif view == "bracket":
            stmt = stmt.where(bracket)
        rows, total = paginate(
            s, stmt.order_by(Set.completed_at.desc().nullslast(), Set.id), page, page_size
        )
        sides = {}
        for side, name in s.execute(
            select(SetSide, EventEntrant.name)
            .outerjoin(EventEntrant, EventEntrant.id == SetSide.entrant_id)
            .where(SetSide.set_id.in_([r.id for r in rows]))
            .order_by(SetSide.side)
        ):
            sides.setdefault(side.set_id, []).append(
                {
                    "entrant_id": side.entrant_id,
                    "name": name,
                    "score": side.score,
                    "is_winner": side.is_winner,
                }
            )
        return page_result(
            [
                {
                    **{
                        k: getattr(r, k)
                        for k in (
                            "id",
                            "resolution",
                            "classification_reason",
                            "stats_eligible",
                            "ranking_eligible",
                            "round_number",
                            "round_label",
                            "completed_at",
                        )
                    },
                    "status": r.lifecycle_status,
                    "source_state": (r.source_result or {}).get("state"),
                    "sides": sides.get(r.id, []),
                }
                for r in rows
            ],
            total,
            page,
            page_size,
        )


def visible_players():
    return select(Player).where(
        select(TournamentParticipant.id)
        .join(Tournament)
        .where(TournamentParticipant.player_id == Player.id, Tournament.published.is_(True))
        .exists()
    )


@router.get("/players", response_model=Page[PlayerView])
def players(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=120),
):
    with Session(request.app.state.engine) as s:
        stmt = visible_players()
        if q:
            stmt = stmt.where(
                Player.tag.icontains(q, autoescape=True)
                | select(PlayerAlias.id)
                .where(
                    PlayerAlias.player_id == Player.id,
                    PlayerAlias.tag.icontains(q, autoescape=True),
                )
                .exists()
            )
        rows, total = paginate(s, stmt.order_by(Player.tag, Player.id), page, page_size)
        return page_result(rows, total, page, page_size)


@router.get("/players/{id}", response_model=PlayerDetail)
def player(
    request: Request, id: UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)
):
    with Session(request.app.state.engine) as s:
        row = s.scalar(visible_players().where(Player.id == id))
        if not row:
            raise HTTPException(404, "Player not found")
        stmt = (
            select(
                Tournament.id.label("tournament_id"),
                Tournament.name.label("tournament_name"),
                Event.id.label("event_id"),
                Event.name.label("event_name"),
                TournamentParticipant.tag_snapshot.label("tag"),
                EventEntrant.name.label("entrant_name"),
                EventEntrant.placement,
            )
            .select_from(TournamentParticipant)
            .join(Tournament, Tournament.id == TournamentParticipant.tournament_id)
            .join(EntrantMember, EntrantMember.participant_id == TournamentParticipant.id)
            .join(Event, Event.id == EntrantMember.event_id)
            .join(EventEntrant, EventEntrant.id == EntrantMember.entrant_id)
            .where(TournamentParticipant.player_id == id, Tournament.published.is_(True))
        )
        total = s.scalar(select(func.count()).select_from(stmt.subquery()))
        history = (
            s.execute(
                stmt.order_by(Tournament.starts_at.desc().nullslast(), Event.id, EventEntrant.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .mappings()
            .all()
        )
        aliases = s.scalars(
            select(PlayerAlias.tag)
            .where(PlayerAlias.player_id == id)
            .distinct()
            .order_by(PlayerAlias.tag)
        ).all()
        return {
            "id": row.id,
            "tag": row.tag,
            "aliases": aliases,
            "history": page_result(history, total, page, page_size),
            "scopes": player_scopes(s, id),
        }


def player_scopes(session, player_id):
    rows = session.execute(
        select(Game.id, Game.name, Event.team_size)
        .select_from(EntrantMember)
        .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .join(Event, Event.id == EntrantMember.event_id)
        .join(Tournament, Tournament.id == Event.tournament_id)
        .join(Game, Game.id == Event.game_id)
        .where(
            TournamentParticipant.player_id == player_id,
            Tournament.published.is_(True),
            Event.team_size.in_([1, 2]),
            Event.competition_type == Event.team_size,
        )
        .distinct()
        .order_by(Game.name, Game.id, Event.team_size)
    ).all()
    return [
        {"game_id": id, "game_name": name, "mode": "singles" if size == 1 else "doubles"}
        for id, name, size in rows
    ]
