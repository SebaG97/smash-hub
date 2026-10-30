"""Brackets of past events from the imported sets, and of an upcoming one (Mission 25).

Past events need nothing new from start.gg: every imported set keeps its phase group, its
round and the sets its players come from. Only the phase names ("Pools", "Top 8") are read
once per event and stored. Upcoming events get a projected winners bracket from the hub's
published seeding, never from start.gg's own seeds.
"""

import asyncio
import time
from collections import defaultdict

from sqlalchemy import select

from app.brackets.layout import arrange, seed_order
from app.competitions.models import (
    EntrantMember,
    Event,
    EventEntrant,
    Set,
    SetSelection,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.games.models import Character
from app.integrations.models import ExternalMapping
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.teams import service as teams

HIDDEN = {"bye", "placeholder", "conditional_unused"}


def startgg_event_id(session, event_id):
    return session.scalar(
        select(ExternalMapping.external_id).where(
            ExternalMapping.entity_type == "event", ExternalMapping.event_id == event_id
        )
    )


def phase_names(data):
    """{phase group id: {"name", "order"}} from start.gg's event phases."""
    phases = ((data or {}).get("event") or {}).get("phases") or []
    groups = {}
    for phase in phases:
        nodes = (phase.get("phaseGroups") or {}).get("nodes") or []
        for node in nodes:
            name = phase.get("name") or "Bracket"
            if len(nodes) > 1:
                name = f"{name} {node.get('displayIdentifier') or ''}".strip()
            groups[str(node["id"])] = dict(name=name, order=phase.get("phaseOrder") or 0)
    return groups


def _players(session, event, entrant_ids):
    """{entrant id: side fields}: tag, approved prefix of that day, hub player and seed."""
    found = {}
    rule_map = teams.rules(session)
    for entrant, part in session.execute(
        select(EventEntrant, TournamentParticipant)
        .outerjoin(EntrantMember, EntrantMember.entrant_id == EventEntrant.id)
        .outerjoin(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .where(EventEntrant.id.in_(entrant_ids))
        .order_by(EntrantMember.position)
    ):
        if entrant.id in found:
            # Teams: one name for the entrant, no single player to link.
            found[entrant.id].update(tag=entrant.name, id=None, prefix=None)
            continue
        singles = part is not None and event.team_size == 1
        shown = teams.resolve(rule_map, part.prefix) if singles and part.prefix else None
        found[entrant.id] = dict(
            tag=part.tag_snapshot if singles else entrant.name,
            prefix=shown[0] if shown else None,
            id=str(part.player_id) if singles else None,
            seed=entrant.seed,
        )
    return found


def event_bracket(session, event_id):
    """Every phase group of a published event, laid out; None when there is none."""
    event = session.get(Event, event_id)
    if event is None:
        return None
    tournament = session.get(Tournament, event.tournament_id)
    if tournament is None or not tournament.published:
        return None
    sets = session.scalars(select(Set).where(Set.event_id == event.id)).all()
    shown = [s for s in sets if s.resolution not in HIDDEN]
    sides = defaultdict(dict)
    for side in session.scalars(select(SetSide).where(SetSide.set_id.in_([s.id for s in shown]))):
        sides[side.set_id][side.side] = side
    players = _players(
        session,
        event,
        {side.entrant_id for by in sides.values() for side in by.values() if side.entrant_id},
    )
    games = defaultdict(lambda: defaultdict(dict))
    for pick, name, icon in session.execute(
        select(SetSelection, Character.name, Character.image_url)
        .join(Character, Character.id == SetSelection.character_id)
        .where(SetSelection.set_id.in_([s.id for s in shown]))
    ):
        games[pick.set_id][pick.game_number][pick.entrant_id] = (dict(name=name, icon=icon), pick)
    groups = defaultdict(list)
    kinds = {}
    for s in sets:
        source = s.source_result or {}
        group = str((source.get("phaseGroup") or {}).get("id") or "")
        kinds[group] = (source.get("phaseGroup") or {}).get("bracketType")
        node = dict(
            id=str(source.get("id") or s.id),
            round=source.get("round", s.round_number),
            label=source.get("fullRoundText") or s.round_label,
            shown=s.resolution not in HIDDEN,
            prereqs=[
                (str(slot["prereqId"]), slot.get("prereqPlacement"))
                for slot in source.get("slots") or []
                if slot.get("prereqType") == "set" and slot.get("prereqId")
            ],
        )
        if node["shown"]:
            node.update(_set_view(s, sides[s.id], players, games[s.id]))
        groups[group].append(node)
    names = phase_names(event.phases)
    items = []
    for number, (group, nodes) in enumerate(sorted(groups.items()), 1):
        if not any(n["shown"] for n in nodes):
            continue
        known = names.get(group)
        items.append(
            dict(
                id=group,
                name=known["name"] if known else None,
                order=known["order"] if known else number,
                type=kinds.get(group) or "DOUBLE_ELIMINATION",
                **arrange(nodes, kinds.get(group) or "DOUBLE_ELIMINATION"),
            )
        )
    items.sort(key=lambda g: (g["order"], g["name"] or "", g["id"]))
    for number, item in enumerate(items, 1):
        if not item["name"]:
            item["name"] = "Bracket" if len(items) == 1 else f"Fase {number}"
    if not items:
        return None
    return dict(
        event=dict(id=str(event.id), name=event.name, entrants=event.num_entrants),
        tournament=dict(id=str(tournament.id), name=tournament.name),
        projected=False,
        groups=items,
    )


def _set_view(s, by_side, players, games):
    view_sides = []
    for number in (1, 2):
        side = by_side.get(number)
        person = players.get(side.entrant_id) if side and side.entrant_id else None
        picks = [
            games[g][side.entrant_id][0]
            for g in sorted(games)
            if side and side.entrant_id in games[g]
        ]
        view_sides.append(
            dict(
                **(person or dict(tag=None, prefix=None, id=None, seed=None)),
                score=side.score if side else None,
                winner=bool(side and side.is_winner),
                characters=list({c["name"]: c for c in picks}.values()),
            )
        )
    entrants = [by_side.get(n).entrant_id if by_side.get(n) else None for n in (1, 2)]
    detail = []
    for number in sorted(games):
        picks = games[number]
        winner = next(
            (i + 1 for i, e in enumerate(entrants) if e in picks and picks[e][1].won), None
        )
        detail.append(
            dict(
                number=number,
                winner=winner,
                characters=[picks[e][0] if e in picks else None for e in entrants],
            )
        )
    return dict(
        status=s.resolution,
        completed_at=s.completed_at.isoformat() if s.completed_at else None,
        sides=view_sides,
        games=detail,
    )


def projected(people):
    """Winners bracket if every seed holds, from the preview's seeded entrants."""
    seeded = sorted((p for p in people if p.get("seed")), key=lambda p: p["seed"])
    if len(seeded) < 4:
        return None
    by_seed = {p["seed"]: p for p in seeded}
    size = 1
    while size < len(seeded):
        size *= 2
    order = seed_order(size)
    rounds = size.bit_length() - 1
    names = {rounds: "Final de winners", rounds - 1: "Semifinal de winners"}
    if rounds >= 3:
        names[rounds - 2] = "Cuartos de winners"
    nodes, ahead = [], {}
    for r in range(1, rounds + 1):
        for i in range(size >> r):
            if r == 1:
                seeds = [order[2 * i], order[2 * i + 1]]
                prereqs = []
            else:
                seeds = [ahead[(r - 1, 2 * i)], ahead[(r - 1, 2 * i + 1)]]
                prereqs = [(f"w{r - 1}-{2 * i}", 1), (f"w{r - 1}-{2 * i + 1}", 1)]
            real = [s for s in seeds if s in by_seed]
            ahead[(r, i)] = min(real) if real else None
            nodes.append(
                dict(
                    id=f"w{r}-{i}",
                    round=r,
                    label=names.get(r) or f"Winners ronda {r}",
                    shown=len(real) == 2,
                    prereqs=prereqs,
                    status="projected",
                    completed_at=None,
                    sides=[_projected_side(by_seed.get(s)) for s in seeds],
                    games=[],
                )
            )
    laid = arrange(nodes)
    return dict(
        projected=True,
        groups=[
            dict(id="proyeccion", name="Proyección", order=1, type="DOUBLE_ELIMINATION", **laid)
        ],
    )


def _projected_side(person):
    if not person:
        return dict(
            tag=None, prefix=None, id=None, seed=None, score=None, winner=False, characters=[]
        )
    mains = person.get("mains") or []
    return dict(
        tag=person["tag"],
        prefix=person.get("prefix"),
        id=person.get("id"),
        seed=person["seed"],
        score=None,
        winner=False,
        characters=[dict(name=m["character"], icon=m.get("icon")) for m in mains[:1]],
    )


# start.gg's empty bracket of an upcoming event barely changes: read it every 15 minutes.
STRUCTURE_SECONDS = 900
_structures: dict = {}


def first_phase(data):
    """The phase every entrant is seeded into (pools, or the only bracket); None if unset."""
    phases = [p for p in ((data or {}).get("event") or {}).get("phases") or [] if p.get("numSeeds")]
    if not phases:
        return None
    return max(phases, key=lambda p: (p["numSeeds"], -(p.get("phaseOrder") or 0)))


async def fetch_structure(client, event_id):
    """start.gg's preview sets of the event's first phase, one list per phase group."""
    data = await client.query("event_phases", {"id": event_id})
    first = first_phase(data)
    if first is None:
        return None
    nodes = (first.get("phaseGroups") or {}).get("nodes") or []
    groups = []
    for node in sorted(nodes, key=lambda n: str(n.get("displayIdentifier") or "")):
        sets = await client.pages("phase_group_sets", "phaseGroup", "sets", str(node["id"]))
        name = first.get("name") or "Bracket"
        if len(nodes) > 1:
            name = f"{name} · {node.get('displayIdentifier') or ''}".strip(" ·")
        groups.append(dict(id=str(node["id"]), name=name, sets=sets))
    # start.gg's phaseOrder does not always follow play ("TOP 8" before "TOP 32"): bigger
    # phases come first.
    phases = sorted(
        (p for p in data["event"]["phases"] if p["id"] != first["id"]),
        key=lambda p: (
            -(((p.get("seeds") or {}).get("pageInfo") or {}).get("total") or 0),
            p.get("phaseOrder") or 0,
        ),
    )
    return dict(groups=groups, later=[p["name"] for p in phases if p.get("name")])


def structure(token, event_id):
    """fetch_structure, cached; None when start.gg has no bracket or does not answer."""
    key = str(event_id)
    hit = _structures.get(key)
    if hit and time.monotonic() - hit[0] < STRUCTURE_SECONDS:
        return hit[1]

    async def fetch():
        async with StartGGClient(token) as client:
            return await fetch_structure(client, key)

    try:
        found = asyncio.run(fetch())
    except ImportFailure:
        return hit[1] if hit else None
    _structures[key] = (time.monotonic(), found)
    return found


def seeded(found, people):
    """Winners side of every group of start.gg's first phase, with the hub's seeds in it.

    Each slot of start.gg's empty bracket names the seed number that goes there, so the
    player with that seed in the hub's seeding takes it. Later rounds show who gets there if
    the better seed always wins.
    """
    by_seed = {p["seed"]: p for p in people if p.get("seed")}
    groups = []
    for group in found["groups"]:
        ahead, nodes = {}, []
        winners = sorted(
            (s for s in group["sets"] if (s.get("round") or 0) > 0), key=lambda s: s["round"]
        )
        for s in winners:
            sides = []
            for slot in s.get("slots") or []:
                # A seed that skips round 1 (bye) is named on its round-2 slot.
                if (slot.get("seed") or {}).get("seedNum"):
                    sides.append(by_seed.get(slot["seed"]["seedNum"]))
                elif slot.get("prereqType") == "set" and slot.get("prereqPlacement") == 1:
                    sides.append(ahead.get(str(slot.get("prereqId"))))
                else:
                    sides.append(None)
            real = [p for p in sides if p]
            ahead[str(s["id"])] = min(real, key=lambda p: p["seed"]) if real else None
            nodes.append(
                dict(
                    id=str(s["id"]),
                    round=s["round"],
                    label=s.get("fullRoundText"),
                    shown=len(real) == 2,
                    prereqs=[
                        (str(slot["prereqId"]), slot.get("prereqPlacement"))
                        for slot in s.get("slots") or []
                        if slot.get("prereqType") == "set" and slot.get("prereqId")
                    ],
                    status="projected",
                    completed_at=None,
                    sides=[_projected_side(p) for p in (sides + [None, None])[:2]],
                    games=[],
                )
            )
        if any(n["shown"] for n in nodes):
            laid = arrange(nodes)
            laid["losers"] = []
            groups.append(
                dict(
                    id=group["id"],
                    name=group["name"],
                    order=len(groups) + 1,
                    type="DOUBLE_ELIMINATION",
                    **laid,
                )
            )
    if not groups:
        return None
    return dict(projected=True, source="startgg", later=found["later"], groups=groups)


def projection(token, event_id, people):
    """start.gg's real first phase with the hub's seeds, or the hub's own winners bracket
    when start.gg has not built one yet."""
    found = structure(token, event_id) if event_id else None
    result = seeded(found, people) if found else None
    if result is None:
        result = projected(people)
        if result:
            result.update(source="hub", later=[])
    return result
