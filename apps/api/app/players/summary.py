"""At-a-glance profile data: ranking place, record and best results (Mission 12)."""

from sqlalchemy import select

from app.competitions.models import (
    EntrantMember,
    Event,
    EventEntrant,
    Tournament,
    TournamentParticipant,
)
from app.players.models import ExternalIdentity


def ranking_place(session, player_id):
    """Place in the first published ranking, matched by the player's start.gg id."""
    from app.seeding.models import SeedingProject, SeedingResult, SeedingRun

    external = session.scalar(
        select(ExternalIdentity.external_id).where(
            ExternalIdentity.player_id == player_id,
            ExternalIdentity.external_id.like("player:%"),
        )
    )
    if external is None:
        return None
    project = session.scalar(
        select(SeedingProject)
        .where(
            SeedingProject.kind == "ranking",
            SeedingProject.published.is_(True),
            SeedingProject.current_run_id.is_not(None),
        )
        .order_by(SeedingProject.event_date.desc())
    )
    if project is None:
        return None
    run = session.get(SeedingRun, project.current_run_id)
    result = session.scalar(
        select(SeedingResult).where(
            SeedingResult.run_id == run.id,
            SeedingResult.startgg_player_id == external.removeprefix("player:"),
        )
    )
    if result is None:
        return None
    method = (run.parameters or {}).get("method", "combined")
    place = (result.metrics.get("ranks") or {}).get(method)
    if not place:
        return None
    return {"slug": project.slug, "name": project.name, "place": place}


def best_results(session, player_id, limit=3):
    """Best final placements in singles, relative to the size of each bracket."""
    rows = session.execute(
        select(
            EventEntrant.placement,
            Event.num_entrants,
            Tournament.id,
            Tournament.name,
            Tournament.starts_at,
        )
        .select_from(EntrantMember)
        .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .join(EventEntrant, EventEntrant.id == EntrantMember.entrant_id)
        .join(Event, Event.id == EntrantMember.event_id)
        .join(Tournament, Tournament.id == Event.tournament_id)
        .where(
            TournamentParticipant.player_id == player_id,
            Tournament.published.is_(True),
            Event.team_size == 1,
            EventEntrant.placement.is_not(None),
        )
    ).all()
    ranked = sorted(
        rows, key=lambda r: (r.placement / max(r.num_entrants or r.placement, 1), r.placement)
    )
    return [
        {
            "placement": r.placement,
            "entrants": r.num_entrants,
            "tournament_id": r.id,
            "tournament_name": r.name,
            "starts_at": r.starts_at,
        }
        for r in ranked[:limit]
    ]
