"""Upload the hub's seeding to start.gg (Mission 30, ADR-019).

The only write the hub makes to start.gg. It is guarded three times: a server switch
(STARTGG_SEEDING_WRITES), a plan the organizer reviews (and whose digest must still match
start.gg when confirming) and the project's slug typed by hand. After writing, start.gg is
read again to check every seed landed where it should.
"""

import hashlib
import json

from app.brackets.service import first_phase
from app.seeding import startgg


class Blocked(Exception):
    """The upload must not happen; the message says why, in Spanish."""


async def read(client, event_slug):
    """The phase every entrant is seeded into and its seeds: [{id, seed, player_id, tag}]."""
    event = await startgg.fetch_event(client, event_slug)
    data = await client.query("event_phases", {"id": event["id"]})
    phase = first_phase(data)
    if phase is None:
        raise Blocked("start.gg todavía no armó las fases de este evento.")
    nodes = await client.pages("pool_seeds", "phase", "seeds", str(phase["id"]))
    seeds = []
    for s in nodes:
        parts = (s.get("entrant") or {}).get("participants") or []
        player = (parts[0].get("player") or {}).get("id") if len(parts) == 1 else None
        seeds.append(
            dict(
                id=str(s["id"]),
                seed=s["seedNum"],
                player_id=str(player) if player else None,
                tag=(s.get("entrant") or {}).get("name"),
            )
        )
    return dict(id=str(phase["id"]), name=phase.get("name") or "Bracket"), seeds


def plan(rows, seeds):
    """start.gg seed numbers in the hub's order; entrants the hub has no seed for go last."""
    by_player = {s["player_id"]: s for s in seeds if s["player_id"]}
    ordered, used = [], set()
    for r in sorted(rows, key=lambda r: r["seed"]):
        found = by_player.get(r["player_id"])
        if found and found["id"] not in used:
            ordered.append(found)
            used.add(found["id"])
    not_seeded = [s for s in sorted(seeds, key=lambda s: s["seed"]) if s["id"] not in used]
    mapping = [dict(seedId=s["id"], seedNum=n) for n, s in enumerate(ordered + not_seeded, 1)]
    current = {s["id"]: s for s in seeds}
    changes = [
        dict(
            tag=current[m["seedId"]]["tag"], before=current[m["seedId"]]["seed"], after=m["seedNum"]
        )
        for m in mapping
        if current[m["seedId"]]["seed"] != m["seedNum"]
    ]
    state = sorted((s["id"], s["seed"]) for s in seeds)
    digest = hashlib.sha256(
        json.dumps([state, [(m["seedId"], m["seedNum"]) for m in mapping]]).encode()
    ).hexdigest()[:16]
    on_startgg = {s["player_id"] for s in seeds}
    return dict(
        mapping=mapping,
        changes=changes,
        unchanged=len(mapping) - len(changes),
        not_seeded=[s["tag"] for s in not_seeded],
        not_on_startgg=[r["gamer_tag"] for r in rows if r["player_id"] not in on_startgg],
        digest=digest,
    )


def check(found, *, enabled, typed, expected_text, digest):
    """Every guard before writing; raises Blocked with the reason."""
    if not enabled:
        raise Blocked(
            "Subir a start.gg está apagado en el servidor (STARTGG_SEEDING_WRITES=true lo activa)."
        )
    if (typed or "").strip() != expected_text:
        raise Blocked(f"Para confirmar hay que escribir exactamente «{expected_text}».")
    if found["not_seeded"]:
        raise Blocked(
            f"{len(found['not_seeded'])} inscriptos de start.gg no tienen seed en el hub "
            f"({', '.join(found['not_seeded'][:5])}): bajá datos nuevos y recalculá antes de subir."
        )
    if digest != found["digest"]:
        raise Blocked(
            "El seeding o start.gg cambiaron desde que revisaste los cambios: revisalos de nuevo."
        )
    if not found["changes"]:
        raise Blocked("start.gg ya tiene este mismo seeding: no hay nada que subir.")


async def write(client, phase, mapping):
    await startgg.update_phase_seeding(client, phase["id"], mapping)


def verify(mapping, seeds):
    """Seeds whose number on start.gg is not the one written."""
    now = {s["id"]: s for s in seeds}
    return [
        dict(
            tag=now[m["seedId"]]["tag"] if m["seedId"] in now else None,
            expected=m["seedNum"],
            found=now[m["seedId"]]["seed"] if m["seedId"] in now else None,
        )
        for m in mapping
        if m["seedId"] not in now or now[m["seedId"]]["seed"] != m["seedNum"]
    ]
