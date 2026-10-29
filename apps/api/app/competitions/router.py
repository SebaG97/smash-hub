"""Public read models. No provider IDs, job internals, or source payloads."""

from datetime import datetime
from typing import Literal, TypeVar
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
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
from app.competitions.roles import event_roles
from app.core.admin import Admin
from app.games.models import Character, Game
from app.players.mains import player_mains
from app.players.models import Player, PlayerAlias
from app.players.summary import best_results, ranking_place
from app.teams import service as teams

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
    images: dict | None = None
    synced_at: datetime | None
    source: str | None
    participant_count: int
    entrant_count: int
    games: list[str]
    counts_for_ranking: bool = True
    seeding_reliable: bool = True


class EventView(PublicModel):
    tournament_id: UUID
    name: str
    game: str
    team_size: int
    competition_type: int | None
    status: str | None
    entrant_count: int
    # Mission 20: the tournament's main bracket (ranking, titles) or a secondary one; null
    # for team events. `main_set` tells whether an organizer decided it.
    main: bool | None = None
    main_set: bool = False


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


class MainView(BaseModel):
    character: str
    icon: str | None = None
    games: int
    share: float
    costume: int = 1


class PlayerView(PublicModel):
    tag: str
    # Most used characters in singles games reported to start.gg (may be empty).
    mains: list[MainView] = []
    # Mission 22: team or prefix of their latest tournaments, when organizers approved it.
    prefix: str | None = None


class ParticipationView(BaseModel):
    tournament_id: UUID
    tournament_name: str
    event_id: UUID
    event_name: str
    tag: str
    entrant_name: str
    placement: int | None


class RankingPlace(BaseModel):
    slug: str
    name: str
    place: int


class BestResult(BaseModel):
    placement: int
    entrants: int | None
    tournament_id: UUID
    tournament_name: str
    starts_at: datetime | None
    event_name: str | None = None
    main: bool = True


class PlayerDetail(PlayerView):
    team: str | None = None  # key of their team page, if the prefix is a team
    aliases: list[str]
    history: Page[ParticipationView]
    scopes: list["PlayerScope"]
    ranking: RankingPlace | None = None
    best_results: list[BestResult] = []


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
                    "images",
                    "synced_at",
                    "counts_for_ranking",
                    "seeding_reliable",
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
    roles = event_roles(s, {r.tournament_id for r in rows})
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
            "main": roles.get(r.id),
            "main_set": r.main is not None,
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
        mains = player_mains(s, [r.id for r in rows], limit=2)
        prefixes = teams.display(s, [r.id for r in rows])
        items = [
            {
                "id": r.id,
                "tag": r.tag,
                "mains": mains.get(r.id, []),
                "prefix": (prefixes.get(r.id) or {}).get("prefix"),
            }
            for r in rows
        ]
        return page_result(items, total, page, page_size)


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
            "mains": player_mains(s, [id], limit=5).get(id, []),
            "prefix": (teams.display(s, [id]).get(id) or {}).get("prefix"),
            "team": (teams.display(s, [id]).get(id) or {}).get("team"),
            "aliases": aliases,
            "history": page_result(history, total, page, page_size),
            "scopes": player_scopes(s, id),
            "ranking": ranking_place(s, id),
            "best_results": best_results(s, id),
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


class CostumeChoice(BaseModel):
    character: str = Field(min_length=1, max_length=120)
    costume: int = Field(ge=1, le=8)


@router.put("/players/{id}/costume", response_model=CostumeChoice)
def set_costume(request: Request, id: UUID, body: CostumeChoice, actor: Admin):
    """Organizers pick which of the 8 costumes share images show for a player's character."""
    with Session(request.app.state.engine) as s:
        player = s.get(Player, id)
        if player is None:
            raise HTTPException(404, "Player not found")
        if not s.scalar(select(Character.id).where(Character.name == body.character).limit(1)):
            raise HTTPException(422, "Unknown character")
        costumes = dict(player.costumes or {})
        if body.costume == 1:
            costumes.pop(body.character, None)
        else:
            costumes[body.character] = body.costume
        player.costumes = costumes
        s.commit()
        return body


IMAGE_BATCH = 30


@router.post("/tournaments/images")
def fetch_tournament_images(request: Request, actor: Admin):
    """Organizer button: read the logo and banner of tournaments imported before Mission 19.

    Read only on start.gg, in batches (about a second per tournament); new imports bring
    their images already.
    """
    import asyncio

    from app.integrations.startgg.client import ImportFailure, StartGGClient
    from app.integrations.startgg.images import tournament_images

    token = request.app.state.settings.startgg_api_token
    if token is None:
        raise HTTPException(503, "Falta el token de start.gg")
    with Session(request.app.state.engine) as s:
        missing = select(Tournament).where(
            Tournament.published.is_(True), Tournament.images.is_(None)
        )
        rows = s.scalars(missing.order_by(Tournament.starts_at.desc()).limit(IMAGE_BATCH)).all()

        async def fetch():
            async with StartGGClient(token) as client:
                return [
                    (await client.query("tournament_images", {"slug": r.slug})).get("tournament")
                    for r in rows
                ]

        try:
            found = asyncio.run(fetch()) if rows else []
        except ImportFailure:
            raise HTTPException(502, "start.gg no respondió") from None
        for row, tournament in zip(rows, found, strict=True):
            row.images = tournament_images((tournament or {}).get("images"))
        s.commit()
        remaining = s.scalar(select(func.count()).select_from(missing.subquery()))
        return {
            "updated": sum(bool(r.images) for r in rows),
            "checked": len(rows),
            "remaining": remaining,
        }


class MainFlag(BaseModel):
    # null hands the decision back to the automatic rule.
    main: bool | None


@router.put("/events/{id}/main", response_model=EventView)
def set_main_flag(request: Request, id: UUID, body: MainFlag, actor: Admin):
    """Organizer checkbox: whether this is the tournament's main bracket. Only main events
    count for rankings, titles, podiums and the player of the month."""
    from app.insights import engine

    with Session(request.app.state.engine) as s:
        event = require_event(s, id)
        event.main = body.main
        event.main_flag_actor, event.main_flag_at = actor, func.now()
        s.flush()
        recalculate_rankings(s, actor)
        s.commit()
        engine.invalidate()
        return event_views(s, [event])[0]


def recalculate_rankings(s, actor):
    """Rankings with data are recalculated at once after an organizer's ranking decision."""
    from app.seeding import service as seeding_service
    from app.seeding.models import SeedingProject

    for project in s.scalars(
        select(SeedingProject).where(
            SeedingProject.kind == "ranking",
            SeedingProject.current_run_id.is_not(None),
            SeedingProject.refresh_status != "RUNNING",
        )
    ):
        seeding_service.recalculate(s, project, actor)


class SeedingFlag(BaseModel):
    reliable: bool


@router.put("/tournaments/{id}/seeding", response_model=TournamentView)
def set_seeding_flag(request: Request, id: UUID, body: SeedingFlag, actor: Admin):
    """Organizer checkbox: a wrongly seeded tournament stops producing upsets."""
    from app.insights import engine

    with Session(request.app.state.engine) as s:
        tournament = require_tournament(s, id)
        tournament.seeding_reliable = body.reliable
        tournament.seeding_flag_actor, tournament.seeding_flag_at = actor, func.now()
        s.commit()
        engine.invalidate()
        return tournament_views(s, [tournament])[0]


class RankingFlag(BaseModel):
    counts: bool


@router.put("/tournaments/{id}/ranking", response_model=TournamentView)
def set_ranking_flag(request: Request, id: UUID, body: RankingFlag, actor: Admin):
    """Organizer checkbox; rankings that already have data are recalculated at once."""
    with Session(request.app.state.engine) as s:
        tournament = require_tournament(s, id)
        tournament.counts_for_ranking = body.counts
        tournament.ranking_flag_actor, tournament.ranking_flag_at = actor, func.now()
        s.flush()
        recalculate_rankings(s, actor)
        s.commit()
        return tournament_views(s, [tournament])[0]
