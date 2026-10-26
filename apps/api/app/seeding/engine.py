"""Pure seeding/ranking calculation: no database, no network.

Every run scores each player with all methods in ``METHODS`` so the page can compare
them; ``Parameters.method`` picks the official order. The default, "combined", mixes two
signals (ADR-011):
- conservative Glicko-2 (rating - k*RD) from the Mission 04 engine: head-to-head strength,
  reliable inside a connected circuit;
- placement score, the mean of log2(field / placement) over the best offline events: the
  only signal comparable across circuits that never play each other.
"""

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.rankings.methods import bradley_terry, elo, wilson_lower_bound
from app.rankings.policy import Policy, utc
from app.rankings.service import calculate

ALGORITHM = "seeding-multi-method-v2"

METHODS = {
    "combined": dict(
        label="Combinado (Glicko-2 + posiciones)",
        description="Promedia el puesto por Glicko-2 conservador y el puesto por posiciones en "
        "torneos. Equilibra enfrentamientos directos con resultados en eventos grandes.",
    ),
    "glicko2": dict(
        label="Glicko-2",
        description="Fuerza por enfrentamientos con incertidumbre (RD). Se ordena por el valor "
        "conservador, rating − k·RD, para no premiar muestras chicas.",
    ),
    "elo": dict(
        label="Elo",
        description="El clásico: cada set suma o resta puntos según quién era favorito, en orden "
        "cronológico. Simple, pero sin medida de incertidumbre.",
    ),
    "bradley_terry": dict(
        label="Bradley-Terry",
        description="Estima la fuerza con todos los enfrentamientos a la vez, sin importar el "
        "orden. Escala tipo Elo: 100 puntos más equivalen a ~64 % de victorias esperadas.",
    ),
    "points": dict(
        label="Puntos por posición",
        description="Estilo circuito: 10·log2(inscritos/posición) por torneo presencial y se suman "
        "los mejores. No mira contra quién se jugó, sí el tamaño del torneo.",
    ),
    "wilson": dict(
        label="% de victorias (Wilson)",
        description="Porcentaje de sets ganados, corregido hacia abajo cuando hay pocos sets "
        "(límite inferior del intervalo de Wilson al 95 %).",
    ),
}
Method = Literal["combined", "glicko2", "elo", "bradley_terry", "points", "wilson"]


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    conservative_k: float = Field(default=2, ge=0, le=4)
    rating_weight: float = Field(default=0.5, ge=0, le=1)
    placement_min_field: int = Field(default=8, ge=2, le=512)
    placement_top_events: int = Field(default=3, ge=1, le=20)
    recent_days: int = Field(default=183, ge=7, le=730)
    spread_flag: int = Field(default=10, ge=1)
    method: Method = "combined"
    elo_k: float = Field(default=32, gt=0, le=100)
    points_top_events: int = Field(default=5, ge=1, le=30)
    # Rankings only list players with enough sets; seeding keeps every entrant.
    min_sets: int = Field(default=0, ge=0, le=200)


def _confidence(sets, offline_events, recent_events, merged):
    sufficient = offline_events >= 3 and sets >= 15 and recent_events >= 1
    if sufficient:
        return "alta" if sets >= 30 and not merged else "media"
    return "baja" if sets else "nula"


def _rank(rows, key):
    ordered = sorted(
        (r for r in rows if r[key] is not None), key=lambda r: (-r[key], r["player_id"])
    )
    return {r["player_id"]: i for i, r in enumerate(ordered, 1)}


def _num(value, digits=0):
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def compute(entrants, sets, *, merges, duplicates, window_start, window_end, parameters=None):
    """entrants: [{player_id, gamer_tag}]; sets: SeedingSet-like dicts. Returns (rows, summary)."""
    p = parameters or Parameters()
    start, end = utc(window_start), utc(window_end)
    recent_from = end - timedelta(days=p.recent_days)
    tags = {e["player_id"]: e["gamer_tag"] for e in entrants}
    seeded = [
        e["player_id"]
        for e in entrants
        if e["player_id"] not in duplicates and e["player_id"] not in merges
    ]

    def canon(pid):
        pid = merges.get(pid, pid) if pid else pid
        return duplicates.get(pid, pid) if pid else pid

    games, wins, losses = [], Counter(), Counter()
    offline_sets, merged_sets = Counter(), Counter()
    circuits = defaultdict(Counter)
    events = defaultdict(dict)  # player -> event -> dict
    used_events, offline_events_all = set(), set()
    for s in sets:
        at = utc(s["played_at"])
        if not start <= at < end:
            continue
        a, b = canon(s["p1_player_id"]), canon(s["p2_player_id"])
        for side, place in ((a, s["p1_placement"]), (b, s["p2_placement"])):
            if side in tags:
                seen = events[side].get(s["startgg_event_id"])
                events[side][s["startgg_event_id"]] = dict(
                    placement=place or (seen or {}).get("placement"),
                    entrants=s["event_entrants"],
                    name=s["tournament_name"],
                    date=min(at, seen["date"]) if seen else at,
                    online=s["online"],
                    counted=(seen or {}).get("counted", False) or s["counted"],
                )
        if not s["counted"] or not a or not b or a == b:
            continue
        used_events.add(s["startgg_event_id"])
        if not s["online"]:
            offline_events_all.add(s["startgg_event_id"])
        a_won = canon(s["winner_player_id"]) == a
        games.append(
            dict(id=s["startgg_set_id"], completed_at=at, players_a=[a], players_b=[b], a_won=a_won)
        )
        for raw, side, won in ((s["p1_player_id"], a, a_won), (s["p2_player_id"], b, not a_won)):
            (wins if won else losses)[side] += 1
            circuits[side]["ONLINE" if s["online"] else (s["country"] or "?")] += 1
            if not s["online"]:
                offline_sets[side] += 1
            if raw != side:
                merged_sets[side] += 1

    computed = calculate(games, Policy(), end)
    ratings = {r["player_id"]: r for r in computed[-1][2]} if computed else {}
    elo_ratings = elo(games, k=p.elo_k)
    bt_ratings = bradley_terry(games)

    rows = []
    for pid in seeded:
        g = ratings.get(pid)
        played = [e for e in events[pid].values() if e["counted"]]
        placements = sorted(
            (
                (math.log2(e["entrants"] / e["placement"]), e)
                for e in played
                if not e["online"]
                and e["entrants"]
                and e["entrants"] >= p.placement_min_field
                and e["placement"]
                and 1 <= e["placement"] <= e["entrants"]
            ),
            key=lambda x: -x[0],
        )[: p.placement_top_events]
        candidates = sorted(
            (
                (10 * math.log2(e["entrants"] / e["placement"]), e)
                for e in played
                if not e["online"]
                and e["entrants"]
                and e["entrants"] >= p.placement_min_field
                and e["placement"]
                and 1 <= e["placement"] <= e["entrants"]
            ),
            key=lambda x: -x[0],
        )[: p.points_top_events]
        sets_total = wins[pid] + losses[pid]
        offline_ev = sum(not e["online"] for e in played)
        recent_ev = sum(e["date"] >= recent_from for e in played)
        last = max((e["date"] for e in played), default=None)
        main = circuits[pid].most_common(1)[0][0] if circuits[pid] else None
        rows.append(
            dict(
                player_id=pid,
                gamer_tag=tags[pid],
                rating=round(g["rating"], 1) if g else None,
                rd=round(g["rd"], 1) if g else None,
                conservative=round(g["rating"] - p.conservative_k * g["rd"], 1) if g else None,
                placement_score=round(sum(x for x, _ in placements) / len(placements), 3)
                if placements
                else None,
                best_placements=[
                    dict(
                        placement=e["placement"],
                        entrants=e["entrants"],
                        tournament=e["name"],
                        date=e["date"].date().isoformat(),
                        score=round(x, 2),
                    )
                    for x, e in placements
                ],
                wins=wins[pid],
                losses=losses[pid],
                sets=sets_total,
                offline_sets=offline_sets[pid],
                events=len(played),
                offline_events=offline_ev,
                recent_events=recent_ev,
                last_event=last.date().isoformat() if last else None,
                circuits=dict(circuits[pid].most_common()),
                main_circuit=main,
                merged_sets=merged_sets[pid],
                confidence=_confidence(sets_total, offline_ev, recent_ev, merged_sets[pid]),
                elo=round(elo_ratings[pid], 1) if pid in elo_ratings else None,
                bradley_terry=round(bt_ratings[pid], 1) if pid in bt_ratings else None,
                points=round(sum(x for x, _ in candidates), 1) if candidates else None,
                points_events=[
                    dict(
                        placement=e["placement"],
                        entrants=e["entrants"],
                        tournament=e["name"],
                        date=e["date"].date().isoformat(),
                        score=round(x, 1),
                    )
                    for x, e in candidates
                ],
                win_rate=round(100 * wins[pid] / sets_total, 1) if sets_total else None,
                wilson=round(wilson_lower_bound(wins[pid], losses[pid]), 1) if sets_total else None,
                eligible=sets_total > 0 and sets_total >= p.min_sets,
            )
        )

    rank_cons, rank_place = _rank(rows, "conservative"), _rank(rows, "placement_score")
    rank_rating = _rank(rows, "rating")
    rated = len(rank_cons)

    def pct(rank):
        return 1 - (rank - 1) / max(rated - 1, 1)

    py_share = Counter(r["main_circuit"] for r in rows if r["main_circuit"]).most_common(1)
    home = py_share[0][0] if py_share else None
    for r in rows:
        pid = r["player_id"]
        r["rank_conservative"], r["rank_placement"] = rank_cons.get(pid), rank_place.get(pid)
        r["rank_rating"] = rank_rating.get(pid)
        if r["rank_conservative"] is None:
            r["combined"] = None
            continue
        if r["rank_placement"] is None:
            r["combined"] = round(pct(r["rank_conservative"]), 4)
        else:
            r["combined"] = round(
                p.rating_weight * pct(r["rank_conservative"])
                + (1 - p.rating_weight) * pct(r["rank_placement"]),
                4,
            )

    keys = dict(
        combined="combined",
        glicko2="conservative",
        elo="elo",
        bradley_terry="bradley_terry",
        points="points",
        wilson="wilson",
    )
    for r in rows:
        r["scores"] = {m: (r[k] if r["eligible"] else None) for m, k in keys.items()}
        r["ranks"] = {}
    for m in METHODS:
        ranked = sorted(
            (r for r in rows if r["scores"][m] is not None),
            key=lambda r, m=m: (-r["scores"][m], -(r["conservative"] or 0), r["player_id"]),
        )
        for i, r in enumerate(ranked, 1):
            r["ranks"][m] = i
    ordered = sorted(
        (r for r in rows if r["scores"][p.method] is not None),
        key=lambda r: r["ranks"][p.method],
    )
    ordered += sorted(
        (r for r in rows if r["scores"][p.method] is None),
        key=lambda r: (not r["eligible"], -r["sets"], r["gamer_tag"].lower()),
    )
    scored = sum(r["scores"][p.method] is not None for r in rows)
    for seed, r in enumerate(ordered, 1):
        r["seed_algorithm"] = seed
        ranks = [x for x in (r["rank_conservative"], r["rank_placement"]) if x is not None]
        r["rank_spread"] = max(ranks) - min(ranks) if len(ranks) == 2 else None
        r["flags"] = _flags(r, p, home, duplicates)
        r["reasons_by_method"] = {m: _reasons(r, p, rated, m) for m in METHODS}
        r["reasons"] = r["reasons_by_method"][p.method]

    summary = dict(
        set_count=len(games),
        event_count=len(used_events),
        offline_event_count=len(offline_events_all),
        player_count=len(ratings),
        rated_entrants=rated,
        scored=scored,
        method=p.method,
        home_circuit=home,
    )
    return ordered, summary


def _flags(r, p, home, duplicates):
    flags = []
    if not r["sets"]:
        flags.append("sin datos: ubicar manualmente")
    elif not r["eligible"]:
        flags.append(f"menos de {p.min_sets} sets")
    if r["main_circuit"] and home and r["main_circuit"] != home:
        flags.append(
            "circuito distinto al local" if r["main_circuit"] != "ONLINE" else "mayoría online"
        )
    if r["sets"] and not r["offline_sets"]:
        flags.append("solo online")
    if r["sets"] and r["confidence"] in ("baja", "nula"):
        flags.append("muestra chica")
    if r["merged_sets"]:
        flags.append(f"IDs fusionados (+{r['merged_sets']} sets)")
    if r["player_id"] in duplicates.values():
        flags.append("tiene una inscripción duplicada omitida")
    if r["rank_spread"] is not None and r["rank_spread"] >= p.spread_flag:
        flags.append(f"rating y posiciones discrepan ({r['rank_spread']} puestos)")
    return flags


def _reasons(r, p, rated, method):
    if not r["sets"]:
        return [
            "No tiene sets contados en la ventana analizada, así que el método no puede ubicarlo. "
            "Va al final en orden alfabético hasta que la organización lo ubique a mano."
        ]
    if not r["eligible"]:
        return [
            f"Tiene {r['sets']} sets contados; hacen falta al menos {p.min_sets} para entrar en "
            "este cálculo."
        ]
    rank = r["ranks"].get(method)
    reasons = [
        f"Resultados: {r['wins']}-{r['losses']} en {r['sets']} sets contados "
        f"({r['offline_sets']} offline), {r['events']} eventos; último el {r['last_event']}.",
    ]
    glicko = (
        f"Glicko-2: {_num(r['rating'])} ± {_num(r['rd'])}. El valor conservador "
        f"(rating − {_num(p.conservative_k)}·RD = {_num(r['conservative'])}) es el "
        f"{r['rank_conservative']}.º de {rated} jugadores con datos."
    )
    if method == "combined":
        reasons.append(glicko)
        if r["rank_placement"] is None:
            reasons.append(
                f"Sin eventos offline de ≥{p.placement_min_field} inscritos: "
                "el puesto sale solo del rating."
            )
        else:
            best = "; ".join(
                f"{b['placement']}/{b['entrants']} {b['tournament']}" for b in r["best_placements"]
            )
            reasons.append(
                f"Posiciones: {_num(r['placement_score'], 2)} rondas superadas en promedio "
                f"({best}); es el {r['rank_placement']}.º puntaje por posiciones."
            )
        weights = (
            "solo rating"
            if r["rank_placement"] is None
            else f"{_num(p.rating_weight * 100)} % rating, "
            f"{_num((1 - p.rating_weight) * 100)} % posiciones"
        )
        reasons.append(f"Combinado ({weights}): {_num(r['combined'], 3)}, que da el puesto {rank}.")
    elif method == "glicko2":
        reasons.append(glicko + f" Con este método queda {rank}.º.")
    elif method == "elo":
        reasons.append(
            f"Elo (K = {_num(p.elo_k)}, todos empiezan en 1.500): {_num(r['elo'])}, el {rank}.º."
        )
    elif method == "bradley_terry":
        reasons.append(
            f"Bradley-Terry: {_num(r['bradley_terry'])} en escala tipo Elo, el {rank}.º. "
            f"Como referencia, su Glicko-2 es {_num(r['rating'])}."
        )
    elif method == "points":
        if r["points"] is None:
            reasons.append(
                f"Sin torneos presenciales de ≥{p.placement_min_field} inscritos: no suma puntos "
                "y va después de los que sí."
            )
        else:
            best = "; ".join(
                f"{b['placement']}/{b['entrants']} {b['tournament']} ({_num(b['score'], 1)})"
                for b in r["points_events"]
            )
            reasons.append(
                f"Puntos: {_num(r['points'], 1)} sumando sus {len(r['points_events'])} mejores "
                f"torneos ({best}); el {rank}.º."
            )
    elif method == "wilson":
        reasons.append(
            f"Ganó el {_num(r['win_rate'], 1)} % de sus sets. Corregido por tamaño de muestra "
            f"(Wilson 95 %): {_num(r['wilson'], 1)} %, el {rank}.º."
        )
    if r["main_circuit"]:
        reasons.append(
            f"Circuito principal: {r['main_circuit']}. Confianza de los datos: {r['confidence']}."
        )
    return reasons


def apply_overrides(rows, overrides):
    """rows ordered by seed_algorithm; overrides: [{player_id, seed, reason, actor}] (pinned seeds)."""
    by_id = {r["player_id"]: r for r in rows}
    pinned = sorted(
        (o for o in overrides if o["player_id"] in by_id), key=lambda o: (o["seed"], o["player_id"])
    )
    pinned_ids = {o["player_id"] for o in pinned}
    final = [dict(r, override=None) for r in rows if r["player_id"] not in pinned_ids]
    for o in pinned:
        row = dict(by_id[o["player_id"]], override=o)
        final.insert(min(o["seed"], len(final) + 1) - 1, row)
    for seed, r in enumerate(final, 1):
        r["seed"] = seed
    return final


def default_window_start(event_date: datetime):
    return event_date - timedelta(days=365)
