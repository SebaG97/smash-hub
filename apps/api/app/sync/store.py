"""start.gg answers -> the local copy (ADR-022). Session work only, no network.

Every function receives an answer that already passed the client's checks (complete,
consistent pagination; no GraphQL errors). Rows are matched by start.gg ID only. A row a
complete answer no longer lists is marked inactive, never deleted; an empty answer where
rows were active is kept as a warning instead, since start.gg wiping a whole event is far
more likely a hiccup than every entrant withdrawing at once.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.sync.models import (
    StartggEntrant,
    StartggEntrantMember,
    StartggEvent,
    StartggPhase,
    StartggPhaseGroup,
    StartggSeed,
    StartggTournament,
)

# event_phases.graphql asks for at most this many pools per phase.
GROUPS_LIMIT = 64


def stamp(value):
    """start.gg's epoch seconds -> aware datetime."""
    return datetime.fromtimestamp(value, UTC) if value else None


def _text(value, size):
    return value[:size] if isinstance(value, str) else value


def _apply(row, values):
    changed = False
    for key, value in values.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    return changed


def upsert(session, model, rows, counts, label, now):
    """rows: {start.gg id: column values}. Inserts new rows, updates changed ones and
    reactivates rows listed again (an entrant who signed up back). Returns {id: row}."""
    found = {}
    if rows:
        found = {r.id: r for r in session.scalars(select(model).where(model.id.in_(list(rows))))}
    for key, values in rows.items():
        row = found.get(key)
        if row is None:
            extra = {"first_seen_at": now} if hasattr(model, "first_seen_at") else {}
            row = model(id=key, active=True, last_seen_at=now, **extra, **values)
            session.add(row)
            found[key] = row
            counts[f"{label}_created"] += 1
            continue
        changed = _apply(row, values)
        if not row.active:
            row.active = True
            if hasattr(row, "removed_at"):
                row.removed_at = None
            changed = True
        row.last_seen_at = now
        if changed:
            counts[f"{label}_updated"] += 1
    return found


def retire(session, model, scope, seen, counts, label, now):
    """Mark inactive the active rows of scope that a complete answer no longer lists."""
    for row in session.scalars(select(model).where(scope, model.active.is_(True))):
        if row.id not in seen:
            row.active = False
            if hasattr(row, "removed_at"):
                row.removed_at = now
            counts[f"{label}_retired"] += 1


# start.gg field -> (column, conversion). Only fields present in an answer are written, so
# the calendar's shorter answer never blanks what a full sync stored.
TOURNAMENT_FIELDS = {
    "name": ("name", lambda v: _text(v, 300)),
    "startAt": ("start_at", stamp),
    "endAt": ("end_at", stamp),
    "state": ("state", lambda v: v),
    "city": ("city", lambda v: _text(v, 120)),
    "venueName": ("venue", lambda v: _text(v, 200)),
    "countryCode": ("country_code", lambda v: (v or None) and v[:2].upper()),
    "numAttendees": ("attendees", lambda v: v),
    "isOnline": ("is_online", lambda v: v),
    "images": ("images", lambda v: v or []),
}
EVENT_FIELDS = {
    "name": ("name", lambda v: _text(v or "?", 300)),
    "slug": ("slug", lambda v: _text(v, 300)),
    "numEntrants": ("num_entrants", lambda v: v),
    "isOnline": ("is_online", lambda v: v),
    "startAt": ("start_at", stamp),
    "state": ("state", lambda v: _text(str(v), 20) if v is not None else None),
    "teamRosterSize": ("team_max_players", lambda v: (v or {}).get("maxPlayers")),
    "videogame": ("videogame_id", lambda v: str((v or {}).get("id") or "") or None),
}


def _fields(node, table):
    return {column: convert(node[key]) for key, (column, convert) in table.items() if key in node}


def tournament(session, node, now, counts, *, reason, events_limit):
    """Store a start.gg tournament and the events it lists. events_limit is the query's
    `events(limit:)`: a list that reaches it may be cut, so nothing is retired then."""
    key = str(node["id"])
    values = _fields(node, TOURNAMENT_FIELDS)
    values["slug"] = (node.get("slug") or "").removeprefix("tournament/")[:160]
    row = session.get(StartggTournament, key)
    if row is None:
        # New tournaments are due right away; an existing one keeps its schedule and an
        # administrator's choice to stop tracking it.
        row = StartggTournament(
            id=key, track_reason=reason, tracked=True, next_sync_at=now, failures=0, **values
        )
        session.add(row)
        counts["tournaments_created"] += 1
    elif _apply(row, values):
        counts["tournaments_updated"] += 1
    if "events" in node:
        events = node.get("events") or []
        rows = {
            str(e["id"]): {"tournament_id": key, **_fields(e, EVENT_FIELDS)}
            for e in events
            if e.get("id") is not None
        }
        upsert(session, StartggEvent, rows, counts, "events", now)
        if len(events) < events_limit:
            session.flush()
            retire(
                session,
                StartggEvent,
                StartggEvent.tournament_id == key,
                set(rows),
                counts,
                "events",
                now,
            )
    session.flush()
    return row


def entrants(session, event, nodes, now, counts, warnings):
    """Store an event's complete list of registrations and their participants."""
    active = session.scalar(
        select(func.count())
        .select_from(StartggEntrant)
        .where(StartggEntrant.event_id == event.id, StartggEntrant.active.is_(True))
    )
    if not nodes and active:
        warnings.append(f"empty_entrants_kept:{event.id}")
        return
    rows, rosters = {}, {}
    for node in nodes:
        key = str(node["id"])
        rows[key] = dict(
            event_id=event.id,
            name=_text(node.get("name") or "?", 300),
            initial_seed=node.get("initialSeedNum"),
        )
        rosters[key] = [
            dict(
                participant_id=str(p["id"]) if p.get("id") is not None else None,
                player_id=str((p.get("player") or {}).get("id") or "") or None,
                gamer_tag=_text(p.get("gamerTag"), 120),
                prefix=_text(p.get("prefix") or None, 120),
                country=_text(((p.get("user") or {}).get("location") or {}).get("country"), 80),
            )
            for p in node.get("participants") or []
        ]
    upsert(session, StartggEntrant, rows, counts, "entrants", now)
    session.flush()
    retire(
        session,
        StartggEntrant,
        StartggEntrant.event_id == event.id,
        set(rows),
        counts,
        "entrants",
        now,
    )
    _rosters(session, rosters, counts)
    event.entrants_synced_at = now
    session.flush()


def _rosters(session, rosters, counts):
    """Each listed entrant's participants become exactly the ones start.gg lists for it."""
    if not rosters:
        return
    existing = {
        (m.entrant_id, m.position): m
        for m in session.scalars(
            select(StartggEntrantMember).where(StartggEntrantMember.entrant_id.in_(list(rosters)))
        )
    }
    for entrant_id, people in rosters.items():
        for position, values in enumerate(people, 1):
            member = existing.pop((entrant_id, position), None)
            if member is None:
                session.add(
                    StartggEntrantMember(entrant_id=entrant_id, position=position, **values)
                )
                counts["participants_created"] += 1
            elif _apply(member, values):
                counts["participants_updated"] += 1
    # Positions start.gg no longer lists for an entrant it did list (a doubles partner
    # change): that entrant's roster is exactly the answer, so the extra slot goes.
    for member in existing.values():
        session.delete(member)
        counts["participants_replaced"] += 1


def _id(value):
    return str(value) if value is not None else None


def phases(session, event, data, seeds, now, counts, warnings):
    """Store an event's phases, their pools and every phase's complete list of seeds.

    data is event_phases.graphql's answer; seeds is {phase id: seed nodes}. A seed that
    changes number or pool updates its row: start.gg keeps the seed's ID.
    """
    listed = ((data or {}).get("event") or {}).get("phases")
    if not isinstance(listed, list):
        warnings.append(f"no_phases_answer:{event.id}")
        return
    known = set(
        session.scalars(
            select(StartggPhase.id).where(
                StartggPhase.event_id == event.id, StartggPhase.active.is_(True)
            )
        )
    )
    if not listed and known:
        warnings.append(f"empty_phases_kept:{event.id}")
        return
    rows = {
        str(p["id"]): dict(
            event_id=event.id,
            name=_text(p.get("name"), 200),
            phase_order=p.get("phaseOrder"),
            bracket_type=_text(p.get("bracketType"), 40),
            num_seeds=p.get("numSeeds"),
            seed_total=(((p.get("seeds") or {}).get("pageInfo") or {}).get("total")),
        )
        for p in listed
    }
    upsert(session, StartggPhase, rows, counts, "phases", now)
    session.flush()
    retire(
        session, StartggPhase, StartggPhase.event_id == event.id, set(rows), counts, "phases", now
    )
    for phase in listed:
        phase_id = str(phase["id"])
        nodes = (phase.get("phaseGroups") or {}).get("nodes") or []
        groups = {
            str(n["id"]): dict(
                phase_id=phase_id, display_identifier=_text(_id(n.get("displayIdentifier")), 40)
            )
            for n in nodes
        }
        upsert(session, StartggPhaseGroup, groups, counts, "pools", now)
        session.flush()
        if len(nodes) < GROUPS_LIMIT:
            retire(
                session,
                StartggPhaseGroup,
                StartggPhaseGroup.phase_id == phase_id,
                set(groups),
                counts,
                "pools",
                now,
            )
        if phase_id in seeds:
            _seeds(session, phase_id, seeds[phase_id], now, counts, warnings)
    event.pools_synced_at = now
    session.flush()


def _seeds(session, phase_id, nodes, now, counts, warnings):
    active = session.scalar(
        select(func.count())
        .select_from(StartggSeed)
        .where(StartggSeed.phase_id == phase_id, StartggSeed.active.is_(True))
    )
    if not nodes and active:
        warnings.append(f"empty_seeds_kept:{phase_id}")
        return
    entrant_ids = {_id((n.get("entrant") or {}).get("id")) for n in nodes} - {None}
    known_entrants = set(
        session.scalars(select(StartggEntrant.id).where(StartggEntrant.id.in_(entrant_ids)))
        if entrant_ids
        else []
    )
    known_groups = set(
        session.scalars(
            select(StartggPhaseGroup.id).where(
                StartggPhaseGroup.id.in_(
                    {_id((n.get("phaseGroup") or {}).get("id")) for n in nodes} - {None}
                )
            )
        )
    )
    rows = {}
    for node in nodes:
        entrant = node.get("entrant") or {}
        people = entrant.get("participants") or []
        group = _id((node.get("phaseGroup") or {}).get("id"))
        origin = node.get("progressionSource") or {}
        rows[str(node["id"])] = dict(
            phase_id=phase_id,
            phase_group_id=group if group in known_groups else None,
            entrant_id=_id(entrant.get("id")) if _id(entrant.get("id")) in known_entrants else None,
            seed_num=node.get("seedNum"),
            group_seed_num=node.get("groupSeedNum"),
            # One player only for singles; teams keep their name and no player.
            player_id=_id((people[0].get("player") or {}).get("id")) if len(people) == 1 else None,
            tag=_text(entrant.get("name"), 300),
            origin_group_id=_id((origin.get("originPhaseGroup") or {}).get("id")),
            origin_placement=origin.get("originPlacement"),
        )
    upsert(session, StartggSeed, rows, counts, "seeds", now)
    session.flush()
    retire(session, StartggSeed, StartggSeed.phase_id == phase_id, set(rows), counts, "seeds", now)
