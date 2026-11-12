"""Prode HTTP: public reading, forecasters' picks and organizers' actions (ADR-020)."""

import asyncio
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import MaybeUser, SignedUser
from app.core.admin import Admin
from app.core.times import LOCAL_PATTERN, from_asuncion
from app.insights import preview
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.links import service as links
from app.prode import engine, service
from app.prode.models import (
    ProdeCandidate,
    ProdeContest,
    ProdePrediction,
    ProdeQuestion,
    ProdeScore,
)

router = APIRouter(prefix="/api/v1/prode", tags=["prode"])
Slug = Annotated[str, Path(pattern=r"^[a-z0-9-]{1,120}$")]
PlayerId = Annotated[str, Field(pattern=r"^\d{1,20}$")]


class Picks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    champion: PlayerId | None = None
    runner_up: PlayerId | None = None
    top8: list[PlayerId] = Field(default_factory=list, max_length=8)


class LocksAt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Date and time in Asunción ("2026-11-14T14:00").
    locks_at: str = Field(pattern=LOCAL_PATTERN)


class Reopen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locks_at: AwareDatetime | None = None


def _session(request):
    return Session(request.app.state.engine, expire_on_commit=False)


def _fail(exc: service.ProdeError):
    raise HTTPException(exc.status, str(exc)) from None


def _iso(value: datetime | None):
    return value.isoformat() if value else None


def _upcoming(request, slug):
    from app.insights.router import _upcoming

    tournament, event, entrants = _upcoming(request, slug)
    if not event:
        raise HTTPException(404, "Ese torneo no tiene un evento de singles de Ultimate.")
    return tournament, event, entrants


def _seeds(s, event):
    order, source, _ = preview.projected_order(s, event.get("slug"))
    return order if source.get("source") == "seeding" else {}


def _contest_for(s, slug):
    return s.scalar(
        select(ProdeContest)
        .where(ProdeContest.tournament_slug == slug, ProdeContest.status != "void")
        .order_by(ProdeContest.created_at.desc())
    )


def _view(s, contest, user):
    """Everything the Prode tab shows. Others' picks stay hidden until the close."""
    status = (
        "locked"
        if contest.status == "open" and service.closed(contest, service._now())
        else contest.status
    )
    candidates = list(
        s.scalars(
            select(ProdeCandidate)
            .where(ProdeCandidate.contest_id == contest.id)
            .order_by(ProdeCandidate.seed.asc().nulls_last(), func.lower(ProdeCandidate.tag))
        )
    )
    hub = preview.hub_players(s, [c.startgg_player_id for c in candidates])
    played = service.picks_of(s, contest)
    mine = played.get(user.id, ({}, None))[0] if user else {}
    questions = {
        q.kind: q
        for q in s.scalars(select(ProdeQuestion).where(ProdeQuestion.contest_id == contest.id))
    }
    ranking = []
    if status != "open":
        scores = {
            sc.user_id: sc
            for sc in s.scalars(select(ProdeScore).where(ProdeScore.contest_id == contest.id))
        }
        users = {u.id: u for u in s.scalars(select(User).where(User.id.in_(list(played))))}
        rows = []
        for user_id, (picks, saved) in played.items():
            score = scores.get(user_id)
            rows.append(
                dict(
                    user_id=user_id,
                    name=users[user_id].display_name if user_id in users else "?",
                    points=score.points if score else 0,
                    exact_hits=score.exact_hits if score else 0,
                    hits=score.hits if score else 0,
                    picks_count=score.picks if score else 0,
                    last_saved_at=saved,
                    picks=picks,
                )
            )
        for row in engine.rank(rows):
            ranking.append(
                dict(
                    rank=row["rank"],
                    user_id=str(row["user_id"]),
                    name=row["name"],
                    points=row["points"],
                    exact_hits=row["exact_hits"],
                    hits=row["hits"],
                    picks=row["picks"],
                )
            )
    return dict(
        id=str(contest.id),
        tournament_slug=contest.tournament_slug,
        name=contest.name,
        event_name=contest.event_name,
        status=status,
        locks_at=_iso(contest.locks_at),
        settled_at=_iso(contest.settled_at),
        rules=contest.rules,
        participants=len(played),
        candidates=[
            dict(
                startgg_player_id=c.startgg_player_id,
                tag=c.tag,
                prefix=c.prefix,
                seed=c.seed,
                id=str(hub[c.startgg_player_id]) if c.startgg_player_id in hub else None,
                withdrawn=c.withdrawn_at is not None,
            )
            for c in candidates
        ],
        mine=dict(
            champion=mine.get("champion"),
            runner_up=mine.get("runner_up"),
            top8=mine.get("top8") or [],
        ),
        results={k: q.result for k, q in questions.items() if q.status == "settled"},
        ranking=ranking,
    )


@router.get("")
def overview(request: Request):
    """Contests and the community leaderboard across settled contests."""
    with _session(request) as s:
        contests = list(
            s.scalars(
                select(ProdeContest)
                .where(ProdeContest.status != "void")
                .order_by(
                    ProdeContest.locks_at.desc().nulls_first(), ProdeContest.created_at.desc()
                )
                .limit(50)
            )
        )
        counts = dict(
            s.execute(
                select(ProdeQuestion.contest_id, func.count(func.distinct(ProdePrediction.user_id)))
                .join(ProdePrediction, ProdePrediction.question_id == ProdeQuestion.id)
                .group_by(ProdeQuestion.contest_id)
            ).all()
        )
        settled = select(ProdeContest.id).where(ProdeContest.status == "settled")
        totals = s.execute(
            select(
                ProdeScore.user_id,
                User.display_name,
                func.sum(ProdeScore.points),
                func.sum(ProdeScore.exact_hits),
                func.sum(ProdeScore.hits),
                func.sum(ProdeScore.picks),
                func.count(),
            )
            .join(User, User.id == ProdeScore.user_id)
            .where(ProdeScore.contest_id.in_(settled), User.disabled_at.is_(None))
            .group_by(ProdeScore.user_id, User.display_name)
        ).all()
        rows = [
            dict(
                user_id=u,
                name=name,
                points=int(points),
                exact_hits=int(exact),
                hits=int(hits),
                picks=int(picks),
                contests=contests_played,
            )
            for u, name, points, exact, hits, picks, contests_played in totals
        ]
        leaderboard = [
            dict(
                rank=r["rank"],
                user_id=str(r["user_id"]),
                name=r["name"],
                points=r["points"],
                contests=r["contests"],
                precision=round(100 * r["hits"] / r["picks"]) if r["picks"] else None,
            )
            for r in engine.rank(rows)[:50]
        ]
        now = service._now()
        return dict(
            contests=[
                dict(
                    id=str(c.id),
                    tournament_slug=c.tournament_slug,
                    name=c.name,
                    status="locked" if c.status == "open" and service.closed(c, now) else c.status,
                    locks_at=_iso(c.locks_at),
                    participants=counts.get(c.id, 0),
                )
                for c in contests
            ],
            leaderboard=leaderboard,
        )


@router.get("/tournaments/{slug}")
def contest(request: Request, slug: Slug, user: MaybeUser):
    """The Prode of a tournament. While open, entrants follow start.gg (cached 15 min)."""
    with _session(request) as s:
        found = _contest_for(s, slug)
        if found is None:
            raise HTTPException(404, "Este torneo todavía no tiene Prode.")
        if found.status == "open":
            service.lock_if_due(s, found)
            if found.status == "open":
                try:
                    _, event, entrants = _upcoming(request, slug)
                    service.sync_candidates(s, found, entrants, _seeds(s, event))
                except HTTPException:
                    pass  # start.gg slow or down: the last known entrants stay
            try:
                s.commit()
            except IntegrityError:
                # Another visit synced the same newcomer first: its copy stands.
                s.rollback()
                found = _contest_for(s, slug)
        return _view(s, found, user)


@router.put("/contests/{contest_id}/picks")
def save_picks(request: Request, contest_id: UUID, picks: Picks, user: SignedUser):
    with _session(request) as s:
        try:
            with s.begin():
                service.save(s, contest_id, user, picks.model_dump())
        except service.ProdeError as exc:
            _fail(exc)
        return _view(s, s.get(ProdeContest, contest_id), user)


@router.get("/users/{user_id}")
def profile(request: Request, user_id: UUID):
    """A forecaster's public profile: achievements, contests and precision."""
    with _session(request) as s:
        user = s.get(User, user_id)
        if user is None or user.disabled_at is not None:
            raise HTTPException(404, "No existe ese pronosticador.")
        history = s.execute(
            select(ProdeScore, ProdeContest)
            .join(ProdeContest, ProdeContest.id == ProdeScore.contest_id)
            .where(ProdeScore.user_id == user.id, ProdeContest.status == "settled")
            .order_by(ProdeContest.settled_at.desc())
        ).all()
        hits = sum(sc.hits for sc, _ in history)
        picks = sum(sc.picks for sc, _ in history)
        player = links.active_player(s, user.id)
        return dict(
            id=str(user.id),
            name=user.display_name,
            player_id=player["id"] if player else None,
            points=sum(sc.points for sc, _ in history),
            contests=len(history),
            precision=round(100 * hits / picks) if picks else None,
            achievements=service.achievements_of(s, [user.id]),
            history=[
                dict(
                    tournament_slug=c.tournament_slug,
                    name=c.name,
                    rank=sc.rank,
                    points=sc.points,
                    hits=sc.hits,
                    picks=sc.picks,
                )
                for sc, c in history
            ],
        )


@router.get("/players/{player_id}/achievements")
def player_achievements(request: Request, player_id: UUID):
    """Prode achievements of a hub player whose linked account plays the Prode."""
    with _session(request) as s:
        users = links.users_for_player(s, player_id)
        return dict(
            user_id=str(users[0]) if users else None,
            achievements=service.achievements_of(s, users) if users else [],
        )


# Organizers (administrator session, ADR-021).


@router.post("/tournaments/{slug}", status_code=201)
def create(request: Request, slug: Slug, actor: Admin):
    tournament, event, entrants = _upcoming(request, slug)
    with _session(request) as s:
        try:
            with s.begin():
                found = service.create(
                    s,
                    slug=slug,
                    tournament=tournament,
                    event=event,
                    entrants=entrants,
                    seeds=_seeds(s, event),
                    actor=actor,
                )
        except service.ProdeError as exc:
            _fail(exc)
        return _view(s, found, None)


def _admin_change(request, contest_id, change):
    with _session(request) as s:
        try:
            with s.begin():
                found = s.get(ProdeContest, contest_id, with_for_update=True)
                if found is None:
                    raise service.ProdeError("No existe ese Prode.", 404)
                change(s, found)
        except service.ProdeError as exc:
            _fail(exc)
        return _view(s, found, None)


@router.post("/contests/{contest_id}/lock")
def lock(request: Request, contest_id: UUID, actor: Admin):
    def change(s, found):
        if found.status != "open":
            raise service.ProdeError("Solo se puede cerrar un Prode abierto.")
        found.status, found.locked_at = "locked", service._now()
        service.audit(s, found, "lock", actor)

    return _admin_change(request, contest_id, change)


@router.post("/contests/{contest_id}/locks-at")
def set_locks_at(request: Request, contest_id: UUID, body: LocksAt, actor: Admin):
    """Change when an open contest closes, in Asunción time (SH-FIX-01). Picks stay."""
    try:
        when = from_asuncion(body.locks_at)
    except ValueError:
        raise HTTPException(422, "Fecha u hora inválida.") from None

    def change(s, found):
        service.set_locks_at(s, found, when, actor, s.scalar(select(func.now())))

    return _admin_change(request, contest_id, change)


@router.post("/contests/{contest_id}/reopen")
def reopen(request: Request, contest_id: UUID, body: Reopen, actor: Admin):
    def change(s, found):
        if found.status not in ("open", "locked"):
            raise service.ProdeError("Un Prode liquidado o anulado no se reabre.")
        found.status, found.locked_at = "open", None
        found.locks_at = body.locks_at
        service.audit(s, found, "reopen", actor, locks_at=_iso(body.locks_at))

    return _admin_change(request, contest_id, change)


@router.post("/contests/{contest_id}/void")
def void(request: Request, contest_id: UUID, actor: Admin):
    def change(s, found):
        found.status = "void"
        service.audit(s, found, "void", actor)

    return _admin_change(request, contest_id, change)


@router.post("/contests/{contest_id}/settle")
def settle(request: Request, contest_id: UUID, actor: Admin):
    """Score everyone from start.gg's final standings. Repeatable after corrections."""
    with _session(request) as s:
        found = s.get(ProdeContest, contest_id)
        if found is None:
            raise HTTPException(404, "No existe ese Prode.")
        event_id = found.startgg_event_id
    placements = _final_placements(request, event_id)
    return _admin_change(
        request,
        contest_id,
        lambda s, c: service.settle(s, c, placements, actor=actor, source="startgg"),
    )


def _final_placements(request, event_id):
    token = request.app.state.settings.startgg_api_token

    async def fetch():
        async with StartGGClient(token) as client:
            return await client.query("live_standings", {"id": event_id})

    try:
        event = (asyncio.run(fetch()) or {}).get("event") or {}
    except ImportFailure:
        raise HTTPException(502, "start.gg no respondió; probá de nuevo en un rato.") from None
    nodes = (event.get("standings") or {}).get("nodes") or []
    placements = {}
    for node in nodes:
        parts = ((node.get("entrant") or {}).get("participants")) or []
        player = (parts[0].get("player") or {}).get("id") if parts else None
        if (
            player
            and node.get("placement")
            and (node.get("isFinal") or event.get("state") == "COMPLETED")
        ):
            placements[str(player)] = node["placement"]
    return placements
