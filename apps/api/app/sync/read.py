"""Reading the local copy of start.gg (ADR-022).

Each reader answers in the shape the start.gg fetchers return, so previews, pools and
brackets are built by the same code whichever side the data came from. A reader returns
None when the local copy has nothing complete for that question yet: only then do callers
ask start.gg live, as before this copy existed.
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.sync.models import (
    StartggEntrant,
    StartggEntrantMember,
    StartggEvent,
    StartggPhase,
    StartggPhaseGroup,
    StartggSeed,
    StartggSet,
    StartggSyncRun,
    StartggTournament,
)

log = logging.getLogger(__name__)


def local(engine, reader, *args):
    """reader(session, *args) on the local copy; None when the database cannot answer, so
    a database hiccup falls back to start.gg instead of failing the page."""
    try:
        with Session(engine) as session:
            return reader(session, *args)
    except SQLAlchemyError:
        log.warning("Local start.gg copy unavailable; asking start.gg", exc_info=True)
        return None


def _epoch(value):
    return int(value.timestamp()) if value else None


def provider_event(row):
    return dict(
        id=row.id,
        name=row.name,
        slug=row.slug,
        numEntrants=row.num_entrants,
        isOnline=row.is_online,
        startAt=_epoch(row.start_at),
        state=row.state,
        teamRosterSize={"maxPlayers": row.team_max_players},
        videogame={"id": row.videogame_id},
    )


def provider_tournament(row, events):
    return dict(
        id=row.id,
        name=row.name,
        slug=f"tournament/{row.slug}",
        # The confirmed start when an administrator set one (SH-FIX-01), else start.gg's.
        startAt=_epoch(row.start_confirmed_at or row.start_at),
        startAtConfirmed=row.start_confirmed_at is not None,
        endAt=_epoch(row.end_at),
        city=row.city,
        venueName=row.venue,
        numAttendees=row.attendees,
        isOnline=row.is_online,
        images=row.images or [],
        events=[provider_event(e) for e in events],
    )


def _events(session, tournament_id):
    return session.scalars(
        select(StartggEvent)
        .where(StartggEvent.tournament_id == tournament_id, StartggEvent.active.is_(True))
        .order_by(StartggEvent.id)
    ).all()


def singles_entrants(session, event_id):
    """Active registrations with exactly one participant who has a start.gg Player.id,
    shaped like seeding.startgg.fetch_entrants. Others (teams, guests without a start.gg
    account) are left out: a hub player is only ever matched by Player.id."""
    by_entrant = {}
    for entrant, member in session.execute(
        select(StartggEntrant, StartggEntrantMember)
        .join(StartggEntrantMember, StartggEntrantMember.entrant_id == StartggEntrant.id)
        .where(StartggEntrant.event_id == event_id, StartggEntrant.active.is_(True))
        .order_by(StartggEntrant.id, StartggEntrantMember.position)
    ):
        by_entrant.setdefault(entrant.id, (entrant, []))[1].append(member)
    rows = []
    for entrant, members in by_entrant.values():
        if len(members) != 1 or not members[0].player_id:
            continue
        member = members[0]
        rows.append(
            dict(
                startgg_entrant_id=entrant.id,
                startgg_player_id=member.player_id,
                gamer_tag=(member.gamer_tag or entrant.name)[:120],
                prefix=member.prefix or None,
                profile_country=member.country,
            )
        )
    return rows


def upcoming(session, slug):
    """What a preview needs: {tournament, event, entrants, synced_at}, or None when the
    tournament or its singles event's registrations were never synced completely."""
    from app.insights.preview import singles_event

    row = session.scalar(select(StartggTournament).where(StartggTournament.slug == slug))
    if row is None:
        return None
    tournament = provider_tournament(row, _events(session, row.id))
    event = singles_event(tournament)
    if event is None:
        if row.last_success_at is None:
            return None
        return dict(tournament=tournament, event=None, entrants=[], synced_at=row.last_success_at)
    stored = session.get(StartggEvent, event["id"])
    if stored.entrants_synced_at is None:
        return None
    return dict(
        tournament=tournament,
        event=event,
        entrants=singles_entrants(session, event["id"]),
        synced_at=stored.entrants_synced_at,
    )


def calendar(session):
    """The country's upcoming tournaments as start.gg listed them at the last discovery,
    or None if no discovery ever completed."""
    last = session.scalar(
        select(StartggSyncRun.finished_at)
        .where(StartggSyncRun.kind == "discovery", StartggSyncRun.status == "completed")
        .order_by(StartggSyncRun.finished_at.desc())
        .limit(1)
    )
    if last is None:
        return None
    rows = session.scalars(
        select(StartggTournament)
        .where(StartggTournament.in_calendar.is_(True), StartggTournament.is_online.is_not(True))
        .order_by(StartggTournament.start_at, StartggTournament.id)
    ).all()
    return dict(
        tournaments=[provider_tournament(r, _events(session, r.id)) for r in rows],
        synced_at=last,
    )


def event_by_slug(session, event_slug):
    if not event_slug:
        return None
    return session.scalar(
        select(StartggEvent)
        .where(StartggEvent.slug == event_slug, StartggEvent.active.is_(True))
        .order_by(StartggEvent.last_seen_at.desc())
        .limit(1)
    )


def phases_data(session, event_id):
    """event_phases.graphql's answer, rebuilt from the active phases and pools."""
    phases = session.scalars(
        select(StartggPhase)
        .where(StartggPhase.event_id == event_id, StartggPhase.active.is_(True))
        .order_by(StartggPhase.phase_order, StartggPhase.id)
    ).all()
    groups = {}
    if phases:
        for group in session.scalars(
            select(StartggPhaseGroup)
            .where(
                StartggPhaseGroup.phase_id.in_([p.id for p in phases]),
                StartggPhaseGroup.active.is_(True),
            )
            .order_by(StartggPhaseGroup.id)
        ):
            groups.setdefault(group.phase_id, []).append(
                dict(id=group.id, displayIdentifier=group.display_identifier)
            )
    return {
        "event": {
            "id": event_id,
            "phases": [
                dict(
                    id=p.id,
                    name=p.name,
                    phaseOrder=p.phase_order,
                    bracketType=p.bracket_type,
                    numSeeds=p.num_seeds,
                    seeds={"pageInfo": {"total": p.seed_total}},
                    phaseGroups={"nodes": groups.get(p.id, [])},
                )
                for p in phases
            ],
        }
    }


def seed_nodes(session, phase_id):
    """A phase's active seeds, shaped like pool_seeds / phase_progressions nodes."""
    return [
        dict(
            id=s.id,
            seedNum=s.seed_num,
            groupSeedNum=s.group_seed_num,
            phaseGroup={"id": s.phase_group_id} if s.phase_group_id else None,
            entrant=dict(
                id=s.entrant_id,
                name=s.tag,
                participants=[{"gamerTag": s.tag, "player": {"id": s.player_id}}]
                if s.player_id
                else [],
            ),
            progressionSource=dict(
                originPlacement=s.origin_placement,
                originPhaseGroup={"id": s.origin_group_id},
            )
            if s.origin_group_id
            else None,
        )
        for s in session.scalars(
            select(StartggSeed)
            .where(StartggSeed.phase_id == phase_id, StartggSeed.active.is_(True))
            .order_by(StartggSeed.seed_num, StartggSeed.id)
        )
    ]


def pools(session, event_slug):
    """{"found": the pools map (seeding.pools.assemble) or None if start.gg has no phase
    yet, "synced_at"}; None when this event's pools were never synced."""
    from app.brackets.service import first_phase
    from app.seeding.pools import assemble

    event = event_by_slug(session, event_slug)
    if event is None or event.pools_synced_at is None:
        return None
    first = first_phase(phases_data(session, event.id))
    if first is None:
        return dict(found=None, synced_at=event.pools_synced_at)
    found = assemble(first, seed_nodes(session, first["id"]), structure_of(session, event))
    return dict(found=found, synced_at=event.pools_synced_at)


def set_nodes(session, group_ids):
    """{pool id: its active sets}, shaped like phase_group_sets nodes, in start.gg's order."""
    result = {}
    if not group_ids:
        return result
    for row in session.scalars(
        select(StartggSet)
        .where(StartggSet.phase_group_id.in_(group_ids), StartggSet.active.is_(True))
        .order_by(StartggSet.phase_group_id, StartggSet.position)
    ):
        result.setdefault(row.phase_group_id, []).append(
            dict(
                id=row.id,
                round=row.round,
                fullRoundText=row.full_round_text,
                state=row.state,
                winnerId=row.winner_entrant_id,
                slots=[
                    dict(
                        prereqId=slot.get("prereqId"),
                        prereqType=slot.get("prereqType"),
                        prereqPlacement=slot.get("prereqPlacement"),
                        seed={"seedNum": slot["seedNum"]} if slot.get("seedNum") else None,
                        entrant={"id": slot["entrantId"]} if slot.get("entrantId") else None,
                    )
                    for slot in row.slots or []
                ],
            )
        )
    return result


def structure_of(session, event):
    """brackets.service.assemble_structure from the copy; None if its sets were never
    synced or start.gg has no phase yet."""
    from app.brackets.service import assemble_structure, first_phase

    if event.sets_synced_at is None:
        return None
    data = phases_data(session, event.id)
    first = first_phase(data)
    if first is None:
        return None
    phases = data["event"]["phases"]
    groups = [g["id"] for p in phases for g in p["phaseGroups"]["nodes"]]
    seeds = {p["id"]: seed_nodes(session, p["id"]) for p in phases if p["id"] != first["id"]}
    return assemble_structure(data, set_nodes(session, groups), seeds)


def structure(session, event_id):
    """{"structure": the bracket structure or None if start.gg has no phase yet,
    "synced_at"}; None when this event's sets were never synced."""
    event = session.get(StartggEvent, event_id)
    if event is None or not event.active or event.sets_synced_at is None:
        return None
    return dict(structure=structure_of(session, event), synced_at=event.sets_synced_at)
