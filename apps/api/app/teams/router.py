"""Teams from start.gg prefixes and the organizers' review of them (Mission 22)."""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.competitions.models import Tournament, TournamentParticipant
from app.core.admin import Admin
from app.insights import engine
from app.insights.router import _with_mains
from app.integrations.models import ExternalMapping
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.teams import service
from app.teams.models import TeamPrefix

router = APIRouter(prefix="/api/v1", tags=["teams"])
PREFIX_BATCH = 8


@router.get("/teams")
def teams(request: Request):
    """Teams approved by the organizers, with members and results of the last year."""
    with Session(request.app.state.engine) as s:
        items = service.teams(s, engine.cached(s))
        for team in items:
            _with_mains(s, team["members"], None)
        return {"items": items}


@router.get("/teams/{key}")
def team(request: Request, key: str):
    with Session(request.app.state.engine) as s:
        found = service.teams(s, engine.cached(s), team_key=key)
        if not found:
            raise HTTPException(404, "Team not found")
        _with_mains(s, found[0]["members"], None)
        return found[0]


@router.get("/prefixes")
def prefixes(request: Request, actor: Admin):
    """Organizers: every prefix seen at a tournament, unreviewed ones first."""
    with Session(request.app.state.engine) as s:
        missing = s.scalar(
            select(func.count())
            .select_from(Tournament)
            .where(Tournament.published.is_(True), Tournament.prefixes_read.is_(False))
        )
        return {"items": service.seen_prefixes(s), "tournaments_to_read": missing}


class PrefixRule(BaseModel):
    status: Literal["team", "alias", "shown", "hidden"]
    name: str | None = Field(default=None, min_length=1, max_length=40)
    # For `alias`: the key of the team it belongs to.
    team: str | None = Field(default=None, max_length=80)


@router.put("/prefixes/{key}")
def set_prefix(request: Request, key: str, body: PrefixRule, actor: Admin):
    """Organizers decide whether a prefix is a team, part of one, shown or hidden."""
    key = service.prefix_key(key)
    if not key:
        raise HTTPException(422, "Prefijo vacío")
    with Session(request.app.state.engine) as s:
        team = None
        if body.status == "alias":
            team = s.get(TeamPrefix, service.prefix_key(body.team) or "")
            if team is None or team.status != "team" or team.key == key:
                raise HTTPException(422, "Elegí un equipo existente para unirlo")
        elif body.status != "team" and s.scalar(
            select(func.count()).select_from(TeamPrefix).where(TeamPrefix.team == key)
        ):
            raise HTTPException(422, "Primero separá los prefijos unidos a este equipo")
        rule = s.get(TeamPrefix, key) or TeamPrefix(key=key)
        rule.status = body.status
        rule.name = (body.name or rule.name or key.upper())[:40]
        rule.team = team.key if team else None
        rule.actor = actor
        rule.updated_at = func.now()
        s.add(rule)
        s.commit()
        return dict(key=rule.key, status=rule.status, name=rule.name, team=rule.team)


@router.post("/prefixes/fetch")
def fetch_prefixes(request: Request, actor: Admin):
    """Organizers: read the prefixes of tournaments imported before they were kept.

    Read only on start.gg, a few tournaments per call; new imports bring them already.
    """
    token = request.app.state.settings.startgg_api_token
    if token is None:
        raise HTTPException(503, "Falta el token de start.gg")
    with Session(request.app.state.engine) as s:
        pending = select(Tournament).where(
            Tournament.published.is_(True), Tournament.prefixes_read.is_(False)
        )
        rows = s.scalars(pending.order_by(Tournament.starts_at.desc()).limit(PREFIX_BATCH)).all()
        ids = dict(
            s.execute(
                select(ExternalMapping.tournament_id, ExternalMapping.external_id).where(
                    ExternalMapping.entity_type == "tournament",
                    ExternalMapping.tournament_id.in_([r.id for r in rows]),
                )
            ).all()
        )

        async def fetch():
            async with StartGGClient(token) as client:
                return [
                    await client.pages("participants", "tournament", "participants", ids[r.id])
                    if r.id in ids
                    else []
                    for r in rows
                ]

        try:
            found = asyncio.run(fetch()) if rows else []
        except ImportFailure:
            raise HTTPException(502, "start.gg no respondió") from None
        updated = 0
        for row, people in zip(rows, found, strict=True):
            by_external = {
                f"tournament:{row.id}:participant:{p['id']}": service.clean_prefix(p.get("prefix"))
                for p in people
            }
            for participant in s.scalars(
                select(TournamentParticipant).where(
                    TournamentParticipant.external_id.in_(list(by_external))
                )
            ):
                participant.prefix = by_external[participant.external_id]
                updated += participant.prefix is not None
            row.prefixes_read = True
        s.commit()
        remaining = s.scalar(select(func.count()).select_from(pending.subquery()))
        return {"checked": len(rows), "with_prefix": updated, "remaining": remaining}
