"""Brackets of past events from the imported sets, and of an upcoming one (Mission 25).

Past events need nothing new from start.gg: every imported set keeps its phase group, its
round and the sets its players come from. Only the phase names ("Pools", "Top 8") are read
once per event and stored. Upcoming events get a projected winners bracket from the hub's
published seeding, never from start.gg's own seeds.
"""

import asyncio
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
from app.core import stale
from app.games.models import Character
from app.integrations.models import ExternalMapping
from app.integrations.startgg.client import ImportFailure, StartGGClient
from app.seeding.startgg import paged
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


async def _group_sets(client, node):
    # Byes included: without them the losers side misses the sets that shape it.
    return await paged(
        client, "phase_group_sets", "phaseGroup", "sets", {"id": str(node["id"])}, per_page=40
    )


def _source(seed):
    origin = seed.get("progressionSource") or {}
    return dict(
        group=str((origin.get("originPhaseGroup") or {}).get("id")),
        placement=origin.get("originPlacement") or 0,
        num=seed.get("seedNum") or 0,
    )


async def fetch_structure(client, event_id):
    """start.gg's preview sets of every phase, in order of play (see assemble_structure)."""
    data = await client.query("event_phases", {"id": event_id})
    first = first_phase(data)
    if first is None:
        return None
    sets, seeds = {}, {}
    for phase in data["event"]["phases"]:
        for node in (phase.get("phaseGroups") or {}).get("nodes") or []:
            sets[str(node["id"])] = await _group_sets(client, node)
        if phase["id"] != first["id"]:
            seeds[str(phase["id"])] = await paged(
                client,
                "phase_progressions",
                "phase",
                "seeds",
                {"id": str(phase["id"])},
                per_page=64,
            )
    return assemble_structure(data, sets, seeds)


def assemble_structure(data, sets, seeds):
    """event_phases' answer, {pool id: set nodes} and {later phase id: seed nodes} -> the
    structure. Shared by the live read and the local copy (ADR-022).

    `groups` are the first phase's (one per pool); `phases` the ones after it, each with
    its groups and, per seed, the pool and placement it is filled from (progressionSource).
    """
    first = first_phase(data)
    if first is None:
        return None
    nodes = (first.get("phaseGroups") or {}).get("nodes") or []
    groups = []
    for node in sorted(nodes, key=lambda n: str(n.get("displayIdentifier") or "")):
        name = first.get("name") or "Bracket"
        if len(nodes) > 1:
            name = f"{name} · {node.get('displayIdentifier') or ''}".strip(" ·")
        groups.append(dict(id=str(node["id"]), name=name, sets=sets.get(str(node["id"]), [])))
    # start.gg's phaseOrder does not always follow play ("TOP 8" before "TOP 32"): bigger
    # phases come first.
    later = sorted(
        (p for p in data["event"]["phases"] if p["id"] != first["id"]),
        key=lambda p: (
            -(((p.get("seeds") or {}).get("pageInfo") or {}).get("total") or 0),
            p.get("phaseOrder") or 0,
        ),
    )
    phases = []
    for phase in later:
        sources = {
            str(seed["id"]): _source(seed)
            for seed in seeds.get(str(phase["id"]), [])
            if (seed.get("progressionSource") or {}).get("originPhaseGroup")
        }
        inner = (phase.get("phaseGroups") or {}).get("nodes") or []
        phase_groups = []
        for node in sorted(inner, key=lambda n: str(n.get("displayIdentifier") or "")):
            name = phase.get("name") or "Bracket"
            if len(inner) > 1:
                name = f"{name} · {node.get('displayIdentifier') or ''}".strip(" ·")
            phase_groups.append(
                dict(id=str(node["id"]), name=name, sets=sets.get(str(node["id"]), []))
            )
        phases.append(dict(name=phase.get("name"), groups=phase_groups, sources=sources))
    return dict(groups=groups, phases=phases, later=[p["name"] for p in later if p.get("name")])


def structure(token, event_id):
    """fetch_structure, refreshed in the background once stale (start.gg takes ~20 s for a
    big bracket); None when start.gg has no bracket or never answered."""
    key = str(event_id)

    def load():
        async def fetch():
            async with StartGGClient(token) as client:
                return await fetch_structure(client, key)

        return asyncio.run(fetch())

    try:
        return stale.cached(_structures, key, STRUCTURE_SECONDS, load)
    except ImportFailure:
        return None


def _play(sets, person_in):
    """Every set of one phase group if the better seed always wins.

    person_in(slot) gives who a seed slot holds. Returns {set id: (sides, winner, loser)}.
    """
    by_id = {str(s["id"]): s for s in sets}
    done = {}

    def outcome(key):
        if key in done:
            return done[key]
        done[key] = ([None, None], None, None)  # guards against a malformed loop
        sides = []
        for slot in by_id[key].get("slots") or []:
            kind, origin = slot.get("prereqType"), str(slot.get("prereqId"))
            if kind == "seed":
                sides.append(person_in(slot))
            elif kind == "set" and origin in by_id:
                _, winner, loser = outcome(origin)
                sides.append(winner if slot.get("prereqPlacement") == 1 else loser)
            elif (slot.get("seed") or {}).get("seedNum"):
                # A seed coming from a bye start.gg left out is named on this slot.
                sides.append(person_in(slot))
            else:  # a bye, or a set start.gg did not send
                sides.append(None)
        real = [p for p in sides if p]
        winner = min(real, key=lambda p: p["seed"]) if real else None
        loser = next((p for p in real if p is not winner), None) if len(real) == 2 else None
        done[key] = (sides, winner, loser)
        return done[key]

    for key in by_id:
        outcome(key)
    return done


def _reset(result):
    """The grand final reset: both slots come from the same set."""
    slots = result.get("slots") or []
    origins = {str(s.get("prereqId")) for s in slots if s.get("prereqType") == "set"}
    return len(slots) == 2 and len(origins) == 1


def _projected_group(group, played, *, order, seeded):
    nodes = []
    for result in group["sets"]:
        if _reset(result):
            continue  # the better seed wins the grand final: no reset
        sides, _, _ = played[str(result["id"])]
        real = [p for p in sides if p]
        nodes.append(
            dict(
                id=str(result["id"]),
                round=result.get("round"),
                label=result.get("fullRoundText"),
                shown=len(real) == 2,
                prereqs=[
                    (str(slot["prereqId"]), slot.get("prereqPlacement"))
                    for slot in result.get("slots") or []
                    if slot.get("prereqType") == "set" and slot.get("prereqId")
                ],
                status="projected",
                completed_at=None,
                sides=[_projected_side(p) for p in (sides + [None, None])[:2]],
                games=[],
            )
        )
    if not any(n["shown"] for n in nodes):
        return None
    return dict(
        id=group["id"],
        name=group["name"],
        order=order,
        type="DOUBLE_ELIMINATION",
        # Only the first phase's opening sets come straight from the seeding.
        seeded=seeded,
        **arrange(nodes),
    )


def _exits(group, played):
    """Who leaves a group for the next phase: winners of the sets nothing in the group
    follows, the winners side first, each side by seed."""
    followed = {
        (str(slot.get("prereqId")), slot.get("prereqPlacement"))
        for result in group["sets"]
        for slot in result.get("slots") or []
        if slot.get("prereqType") == "set"
    }
    out = []
    for result in group["sets"]:
        key = str(result["id"])
        winner = played[key][1]
        if winner and (key, 1) not in followed and not _reset(result):
            out.append(((result.get("round") or 0) < 0, winner["seed"], winner))
    return [p for _, _, p in sorted(out, key=lambda x: (x[0], x[1]))]


def seeded(found, people):
    """start.gg's whole event with the hub's seeds in it, winners and losers of every
    phase, if the better seed always wins.

    Each slot of start.gg's empty first phase names the seed that goes there. Later phases
    name the pool and placement each of their seeds comes from, so whoever leaves a pool
    goes there (the better seed takes the better spot among equal placements).
    """
    by_seed = {p["seed"]: p for p in people if p.get("seed")}
    groups, exits = [], {}

    def first_slot(slot):
        return by_seed.get((slot.get("seed") or {}).get("seedNum"))

    for group in found["groups"]:
        played = _play(group["sets"], first_slot)
        exits[group["id"]] = _exits(group, played)
        laid = _projected_group(group, played, order=len(groups) + 1, seeded=True)
        if laid:
            groups.append(laid)
    if not groups:
        return None
    # Phases start.gg cannot fill yet (no progressions) stay as names.
    later = [] if "phases" in found else list(found.get("later") or [])
    for phase in found.get("phases") or []:
        filled = {}
        for origin, leaving in exits.items():
            spots = sorted(
                (s for s in phase["sources"].items() if s[1]["group"] == origin),
                key=lambda s: (s[1]["placement"], s[1]["num"]),
            )
            filled.update((seed_id, p) for (seed_id, _), p in zip(spots, leaving, strict=False))
        if not filled:
            later.append(phase["name"])
            continue
        next_exits = {}
        for group in phase["groups"]:
            played = _play(group["sets"], lambda slot, f=filled: f.get(str(slot.get("prereqId"))))
            next_exits[group["id"]] = _exits(group, played)
            laid = _projected_group(group, played, order=len(groups) + 1, seeded=False)
            if laid:
                groups.append(laid)
        exits = next_exits
    return dict(projected=True, source="startgg", later=later, groups=groups)


def projection(token, event_id, people, engine=None):
    """start.gg's real first phase with the hub's seeds, or the hub's own winners bracket
    when start.gg has not built one yet. With an engine, the local copy of start.gg answers
    first (ADR-022); start.gg is asked only for brackets never synced."""
    local = None
    if engine is not None and event_id:
        from app.sync import read as synced

        local = synced.local(engine, synced.structure, str(event_id))
    if local is not None:
        found = local["structure"]
    else:
        found = structure(token, event_id) if event_id else None
    result = seeded(found, people) if found else None
    if result is None:
        result = projected(people)
        if result:
            result.update(source="hub", later=[])
    return result
