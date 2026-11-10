"""Seeding by pools (Mission 29).

Organizers think in pools: who lands in each one and who meets whom in the first round.
start.gg decides the pool of every seed number when it builds the phase, so the hub reads
that map (read only), places its own seeding on it and turns moves between pools into
seed swaps. start.gg's current seeding can also be copied into the hub as manual moves.
"""

import asyncio
import time
from datetime import timedelta

from app.brackets.service import fetch_structure, first_phase
from app.core import stale
from app.integrations.startgg.client import StartGGClient
from app.seeding import startgg
from app.seeding.models import SeedingOverride

CACHE_SECONDS = 120
REMATCH_DAYS = 45
_cache: dict = {}


async def fetch(client, event_slug):
    """start.gg's first phase: its pools, who holds each seed and the first-round pairs."""
    event = await startgg.fetch_event(client, event_slug)
    data = await client.query("event_phases", {"id": event["id"]})
    first = first_phase(data)
    if first is None:
        return None
    seeds = await client.pages("pool_seeds", "phase", "seeds", str(first["id"]))
    structure = await fetch_structure(client, event["id"])
    pairs = []
    for group in (structure or {}).get("groups") or []:
        for result in group["sets"]:
            numbers = [(s.get("seed") or {}).get("seedNum") for s in result.get("slots") or []]
            if result.get("round") == 1 and len(numbers) == 2 and all(numbers):
                pairs.append(numbers)
    nodes = (first.get("phaseGroups") or {}).get("nodes") or []
    return dict(
        phase=first.get("name") or "Pools",
        groups=[
            dict(id=str(n["id"]), name=str(n.get("displayIdentifier") or i))
            for i, n in enumerate(sorted(nodes, key=lambda n: str(n.get("displayIdentifier"))), 1)
        ],
        seeds=[
            dict(
                seed=s["seedNum"],
                group=str((s.get("phaseGroup") or {}).get("id")),
                pool_seed=s.get("groupSeedNum"),
                player_id=str(
                    (
                        (((s.get("entrant") or {}).get("participants") or [{}])[0]).get("player")
                        or {}
                    ).get("id")
                    or ""
                )
                or None,
                tag=(s.get("entrant") or {}).get("name"),
            )
            for s in seeds
        ],
        pairs=pairs,
    )


def read(token, event_slug, fresh=False):
    """fetch, kept two minutes so moving players does not wait on start.gg every time."""
    hit = _cache.get(event_slug)
    if hit and not fresh and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]

    async def run():
        async with StartGGClient(token) as client:
            return await fetch(client, event_slug)

    found = asyncio.run(run())
    _cache[event_slug] = (time.monotonic(), found)
    return found


def read_public(token, event_slug):
    """read for the public preview: never waits on start.gg (~30 s) once read before; a
    stale copy answers while a background refresh brings the organizers' moves in."""

    def load():
        async def run():
            async with StartGGClient(token) as client:
                return await fetch(client, event_slug)

        return asyncio.run(run())

    return stale.cached(_cache, event_slug, CACHE_SECONDS, load)


def build(rows, found, *, hub=None, teams=None, ranked=(), matches=(), tags=None):
    """The hub's seeding laid on start.gg's pools.

    rows: the hub's final seeding (seed, player_id = start.gg id, gamer_tag, prefix, mains,
    rating). hub maps start.gg ids to hub players, teams hub players to their team key,
    ranked lists hub players of the published ranking in order and matches are the hub's
    results (for recent rematches).
    """
    hub, teams, tags = hub or {}, teams or {}, tags or {}
    place = {s["seed"]: s for s in found["seeds"]}
    on_startgg = {s["player_id"]: s["seed"] for s in found["seeds"] if s["player_id"]}
    ranking = {player: i for i, player in enumerate(ranked, 1)}
    pools = {
        g["id"]: dict(id=g["id"], name=f"Pool {g['name']}", players=[]) for g in found["groups"]
    }
    outside, by_seed = [], {}
    for r in rows:
        player = hub.get(r["player_id"])
        item = dict(
            seed=r["seed"],
            player_id=r["player_id"],
            tag=r["gamer_tag"],
            prefix=r.get("prefix"),
            mains=(r.get("mains") or [])[:1],
            circuit=r.get("main_circuit"),
            country=r.get("country"),
            rating=r.get("rating"),
            ranking=ranking.get(player),
            startgg_seed=on_startgg.get(r["player_id"]),
        )
        by_seed[r["seed"]] = (item, player)
        spot = place.get(r["seed"])
        if spot and spot["group"] in pools:
            pools[spot["group"]]["players"].append(item | dict(pool_seed=spot["pool_seed"]))
        else:
            outside.append(item)
    for pool in pools.values():
        players = pool["players"]
        players.sort(key=lambda p: p["pool_seed"] or 0)
        ratings = [p["rating"] for p in players if p["rating"] is not None]
        pool["top20"] = sum(1 for p in players if p["ranking"] and p["ranking"] <= 20)
        pool["rating"] = round(sum(ratings) / len(ratings)) if ratings else None
    warnings = []
    last_seen = {}
    latest = max((m.at for m in matches), default=None)
    for m in matches:
        if latest and latest - m.at <= timedelta(days=REMATCH_DAYS):
            last_seen[frozenset((m.winner, m.loser))] = m
    for a, b in found["pairs"]:
        if a not in by_seed or b not in by_seed:
            continue
        (pa, ha), (pb, hb) = by_seed[a], by_seed[b]
        names = f"{pa['tag']} (seed {a}) y {pb['tag']} (seed {b})"
        if ha and hb and teams.get(ha) and teams.get(ha) == teams.get(hb):
            warnings.append(
                dict(
                    kind="team",
                    seeds=[a, b],
                    text=f"Compañeros de equipo en primera ronda: {names}.",
                )
            )
        met = last_seen.get(frozenset((ha, hb))) if ha and hb else None
        if met:
            warnings.append(
                dict(
                    kind="rematch",
                    seeds=[a, b],
                    text=f"Revancha en primera ronda: {names} se cruzaron en {met.tournament}.",
                )
            )
    seeded = {r["player_id"] for r in rows}
    return dict(
        phase=found["phase"],
        pools=list(pools.values()),
        outside=outside,
        warnings=warnings,
        # Signed up on start.gg after the hub's last download: they have no seed here yet.
        missing=[
            s["tag"] for s in found["seeds"] if s["player_id"] and s["player_id"] not in seeded
        ],
        startgg_seeded=bool(on_startgg),
    )


def adopt(session, project, rows, found, actor, audit):
    """Copy start.gg's current order into the hub as manual moves (replacing the others)."""
    on_startgg = {s["player_id"]: s["seed"] for s in found["seeds"] if s["player_id"]}
    known = {r["player_id"] for r in rows}
    session.query(SeedingOverride).filter(SeedingOverride.project_id == project.id).delete()
    placed = 0
    for player, seed in sorted(on_startgg.items(), key=lambda x: x[1]):
        if player in known:
            session.add(
                SeedingOverride(
                    project_id=project.id,
                    startgg_player_id=player,
                    seed=seed,
                    reason="Seeding cargado en start.gg",
                    actor=actor,
                )
            )
            placed += 1
    # Players no longer signed up on start.gg go after everyone who is.
    last = max(on_startgg.values(), default=0)
    extra = [r for r in rows if r["player_id"] not in on_startgg]
    for i, r in enumerate(extra, 1):
        session.add(
            SeedingOverride(
                project_id=project.id,
                startgg_player_id=r["player_id"],
                seed=last + i,
                reason="No figura inscripto en start.gg",
                actor=actor,
            )
        )
    missing = [s["tag"] for s in found["seeds"] if s["player_id"] and s["player_id"] not in known]
    audit(session, project, "adopt_startgg", actor, placed=placed, missing=len(missing))
    return dict(placed=placed, missing=missing, not_signed_up=[r["gamer_tag"] for r in extra])
