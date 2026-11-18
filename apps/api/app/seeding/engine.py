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

from app.rankings.methods import (
    bradley_terry,
    elo,
    glicko1,
    weighted_bradley_terry,
    wilson_lower_bound,
)
from app.rankings.policy import Policy, period_start, utc
from app.rankings.service import calculate

ALGORITHM = "seeding-multi-method-v3"

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
    "glicko1": dict(
        label="Glicko-1",
        description="La versión original de Glicko (1999): rating con incertidumbre (RD) que "
        "crece con la inactividad, sin la volatilidad de Glicko-2. Se ordena por rating − 2·RD.",
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
    "weighted_bt": dict(
        label="Bradley-Terry ponderado",
        description="Bradley-Terry donde cada set pesa distinto: la mitad cada 90 días, el "
        "online al 1 % y los cruces repetidos con el mismo rival suman cada vez menos. Con "
        "pocos sets recientes el valor queda cerca de 1.500.",
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
Method = Literal[
    "combined", "glicko2", "glicko1", "elo", "bradley_terry", "weighted_bt", "points", "wilson"
]


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
    # Weighted Bradley-Terry: half-life of a set and weight of an online set.
    half_life_days: float = Field(default=90, gt=0, le=3650)
    online_weight: float = Field(default=0.01, ge=0, le=1)
    # Rankings only list players with enough sets; seeding keeps every entrant.
    min_sets: int = Field(default=0, ge=0, le=200)
    # Mission 24: rankings ask for offline tournaments played (not sets, which punish
    # whoever loses early) and for one of them in the last `active_days` (0: no limit).
    min_events: int = Field(default=0, ge=0, le=50)
    active_days: int = Field(default=0, ge=0, le=730)


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


def compute(
    entrants,
    sets,
    *,
    merges,
    duplicates,
    window_start,
    window_end,
    parameters=None,
    foreign=(),
):
    """entrants: [{player_id, gamer_tag}]; sets: SeedingSet-like dicts. Returns (rows, summary).

    `foreign`: start.gg ids organizers flagged with another country. Rankings measure the
    local scene, so they are never eligible; their sets still count for everyone else.
    """
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

    foreign = {canon(pid) for pid in foreign}

    games, wins, losses = [], Counter(), Counter()
    offline_sets, merged_sets = Counter(), Counter()
    circuits = defaultdict(Counter)
    events = defaultdict(dict)  # player -> event -> dict
    results = defaultdict(list)  # player -> [(opponent, won)], for the reasons
    other_tags = {}  # tags of opponents who are not entrants
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
            dict(
                id=s["startgg_set_id"],
                completed_at=at,
                players_a=[a],
                players_b=[b],
                a_won=a_won,
                online=bool(s["online"]),
                event_id=s["startgg_event_id"],
            )
        )
        other_tags.setdefault(a, s.get("p1_tag"))
        other_tags.setdefault(b, s.get("p2_tag"))
        results[a].append((b, a_won))
        results[b].append((a, not a_won))
        for raw, side, won in ((s["p1_player_id"], a, a_won), (s["p2_player_id"], b, not a_won)):
            (wins if won else losses)[side] += 1
            circuits[side]["ONLINE" if s["online"] else (s["country"] or "?")] += 1
            if not s["online"]:
                offline_sets[side] += 1
            if raw != side:
                merged_sets[side] += 1

    # Glicko-2 rates weekly periods and skips the one still open, so a window ending
    # mid-week (a month's end) used to leave out that week's tournaments. Closing the
    # period at the end of that week counts them; sets after `end` were dropped above.
    policy = Policy()
    closed = period_start(end - timedelta(microseconds=1), policy)
    computed = calculate(games, policy, closed + timedelta(days=policy.period_days))
    ratings = {r["player_id"]: r for r in computed[-1][2]} if computed else {}
    elo_ratings = elo(games, k=p.elo_k)
    g1_ratings = glicko1(games)
    bt_ratings = bradley_terry(games)
    wbt_ratings = weighted_bradley_terry(
        games, end=end, half_life_days=p.half_life_days, online_weight=p.online_weight
    )

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
        last_offline = max((e["date"] for e in played if not e["online"]), default=None)
        missing = []
        if sets_total < max(p.min_sets, 1):
            missing.append("sets")
        if offline_ev < p.min_events:
            missing.append("events")
        if p.active_days and (
            last_offline is None or last_offline < end - timedelta(days=p.active_days)
        ):
            missing.append("inactive")
        if pid in foreign:
            missing.append("foreign")
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
                glicko1=round(g1_ratings[pid][0], 1) if pid in g1_ratings else None,
                glicko1_rd=round(g1_ratings[pid][1], 1) if pid in g1_ratings else None,
                glicko1_conservative=round(g1_ratings[pid][0] - 2 * g1_ratings[pid][1], 1)
                if pid in g1_ratings
                else None,
                bradley_terry=round(bt_ratings[pid], 1) if pid in bt_ratings else None,
                weighted_bt=round(wbt_ratings[pid], 1) if pid in wbt_ratings else None,
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
                eligible=not missing,
                # What keeps an ineligible player out: "sets", "events", "inactive" or
                # "foreign" (flagged with another country by organizers).
                missing=missing,
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
        glicko1="glicko1_conservative",
        elo="elo",
        bradley_terry="bradley_terry",
        weighted_bt="weighted_bt",
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
    # Reasons speak of places in the ranking readers see: eligible players only.
    by_place = sorted(
        (r for r in rows if r["eligible"] and r["placement_score"] is not None),
        key=lambda r: (-r["placement_score"], r["player_id"]),
    )
    context = dict(
        results=results,
        names={**{k: v for k, v in other_tags.items() if v}, **tags},
        strength={pid: g["rating"] for pid, g in ratings.items()},
        ranks={r["player_id"]: r["ranks"] for r in rows},
        placement_rank={r["player_id"]: i for i, r in enumerate(by_place, 1)},
    )
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
        r["played_events"] = sorted(
            (e for e in events[r["player_id"]].values() if e["counted"] and not e["online"]),
            key=lambda e: e["date"],
            reverse=True,
        )
        r["reasons_by_method"] = {m: _reasons(r, p, context, m) for m in METHODS}
        r["reasons"] = r["reasons_by_method"][p.method]
        del r["played_events"]

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
        flags.extend(
            {
                "sets": f"menos de {p.min_sets} sets",
                "events": f"menos de {p.min_events} torneos",
                "inactive": f"sin torneos en {p.active_days} días",
                "foreign": "jugador de otro país",
            }[m]
            for m in r["missing"]
        )
    if r["main_circuit"] and home and r["main_circuit"] != home:
        flags.append(
            "circuito distinto al local" if r["main_circuit"] != "ONLINE" else "mayoría online"
        )
    if r["sets"] and not r["offline_sets"]:
        flags.append("solo online")
    if r["sets"] and r["confidence"] in ("baja", "nula"):
        flags.append("pocos datos todavía")
    if r["merged_sets"]:
        flags.append(f"IDs fusionados (+{r['merged_sets']} sets)")
    if r["player_id"] in duplicates.values():
        flags.append("tiene una inscripción duplicada omitida")
    if r["rank_spread"] is not None and r["rank_spread"] >= p.spread_flag:
        flags.append(f"rating y posiciones discrepan ({r['rank_spread']} puestos)")
    return flags


def _day(value):
    return value.strftime("%d/%m/%Y")


def _list(items, limit):
    shown = ", ".join(items[:limit])
    rest = len(items) - limit
    return f"{shown} y {rest} más" if rest > 0 else shown


def _opponents(r, context, method, won):
    """Opponents beaten (or lost to), strongest first, with their place in the ranking."""
    count = Counter(opp for opp, w in context["results"][r["player_id"]] if w == won)
    strength = context["strength"]
    ordered = sorted(count, key=lambda o: (-strength.get(o, float("-inf")), str(o)))
    out = []
    for opp in ordered:
        name = context["names"].get(opp) or "jugador sin tag"
        place = context["ranks"].get(opp, {}).get(method)
        text = f"{name} ({place}.º)" if place else name
        out.append(f"{text} ×{count[opp]}" if count[opp] > 1 else text)
    return out


def _reasons(r, p, context, method):
    """What a reader needs to understand the place, in plain words and with the data."""
    if not r["sets"]:
        return [
            "No tiene sets contados en la ventana analizada, así que el método no puede ubicarlo. "
            "Va al final en orden alfabético hasta que la organización lo ubique a mano."
        ]
    if not r["eligible"]:
        why = {
            "sets": f"tiene {r['sets']} sets contados y hacen falta al menos {p.min_sets}",
            "events": f"jugó {r['offline_events']} "
            f"{'torneo presencial' if r['offline_events'] == 1 else 'torneos presenciales'} "
            f"y hacen falta al menos {p.min_events}",
            "inactive": f"no juega un torneo presencial desde el {r['last_event']}; hace falta "
            f"al menos uno en los últimos {p.active_days} días",
            "foreign": "la organización lo marcó como jugador de otro país, y el ranking mide "
            "solo a la escena local (sus sets sí cuentan para los demás)",
        }
        return [f"No entra en este cálculo: {'; '.join(why[m] for m in r['missing'])}."]
    rank = r["ranks"].get(method)
    torneos = "torneo presencial" if r["offline_events"] == 1 else "torneos presenciales"
    online = r["sets"] - r["offline_sets"]
    summary = (
        f"Ganó {r['wins']} de sus {r['sets']} sets ({_num(r['win_rate'])} %) en "
        f"{r['offline_events']} {torneos}"
        + (f", más {online} sets online" if online else "")
        + (f"; el último, el {_day(r['played_events'][0]['date'])}." if r["played_events"] else ".")
    )
    reasons = [summary]

    glicko = (
        f"Por a quién le ganó y con quién perdió: {_num(r['conservative'])} puntos (Glicko-2). "
        "Ganarle a alguien de arriba suma mucho y perder con alguien de abajo resta mucho. "
        "Como el sistema todavía no está seguro de su nivel exacto, le descuenta un margen: "
        f"{_num(r['rating'])} − {_num(p.conservative_k)} × {_num(r['rd'])} = "
        f"{_num(r['conservative'])}. Ese margen se achica a medida que juega más."
    )
    if method == "combined":
        g_rank = r["ranks"].get("glicko2")
        p_rank = context["placement_rank"].get(r["player_id"])
        if p_rank is None:
            reasons.append(
                glicko + f" No tiene torneos presenciales de {p.placement_min_field} o más "
                f"inscritos, así que su puesto sale solo de esto: {rank}.º."
            )
        else:
            reasons.append(
                f"El puesto mezcla dos cosas: a quién le ganó ({_num(p.rating_weight * 100)} %) "
                f"y hasta dónde llegó en los torneos ({_num(100 - p.rating_weight * 100)} %). "
                f"Por lo primero sería {g_rank}.º y por lo segundo {p_rank}.º; combinadas "
                f"queda {rank}.º."
            )
            reasons.append(glicko)
            reasons.append(
                f"Hasta dónde llegó: se promedian sus {p.placement_top_events} mejores torneos "
                f"de {p.placement_min_field} o más inscritos, y cuenta más llegar lejos en un "
                "torneo grande (ganar uno de 32 vale 5; top 8 de 32 vale 2). Su promedio: "
                f"{_num(r['placement_score'], 2)}."
            )
    elif method == "glicko2":
        reasons.append(glicko + f" Con eso queda {rank}.º.")
    elif method == "glicko1":
        reasons.append(
            f"Por a quién le ganó y con quién perdió: {_num(r['glicko1_conservative'])} puntos "
            f"(Glicko-1, ya con el margen por pocos datos: {_num(r['glicko1'])} − 2 × "
            f"{_num(r['glicko1_rd'])}). Queda {rank}.º."
        )
    elif method == "elo":
        reasons.append(
            f"Elo: {_num(r['elo'])} puntos. Todos empiezan en 1.500 y en cada set el ganador le "
            "saca puntos al perdedor: muchos si no era favorito, pocos si lo era. "
            f"Queda {rank}.º."
        )
    elif method == "bradley_terry":
        reasons.append(
            f"Bradley-Terry: {_num(r['bradley_terry'])} puntos. Mira todos los sets juntos y "
            "busca el nivel de cada jugador que mejor explica quién le ganó a quién. 1.500 es "
            "el promedio y 100 puntos más que un rival equivalen a ganarle unas 2 de cada 3 "
            f"veces. Queda {rank}.º."
        )
    elif method == "weighted_bt":
        online_share = p.online_weight * 100
        reasons.append(
            f"Bradley-Terry ponderado: {_num(r['weighted_bt'])} puntos (sin ponderar serían "
            f"{_num(r['bradley_terry'])}). Igual que Bradley-Terry, pero los sets recientes "
            f"valen más (cada {_num(p.half_life_days)} días un set vale la mitad), el online "
            f"vale el {_num(online_share, 0 if online_share >= 1 else 1)} % y jugar muchas "
            "veces con el mismo rival suma cada vez menos. Con pocos sets recientes, el "
            f"puntaje queda cerca de 1.500. Queda {rank}.º."
        )
    elif method == "points":
        if r["points"] is None:
            reasons.append(
                f"Sin torneos presenciales de {p.placement_min_field} o más inscritos: no suma "
                "puntos y va después de los que sí."
            )
        else:
            reasons.append(
                f"Puntos: {_num(r['points'], 1)}, la suma de sus {len(r['points_events'])} "
                "mejores torneos. Cada torneo da más cuanto más lejos llegó y más grande era: "
                f"ganar uno de 32 da 50 y top 8 de 32 da 20. Queda {rank}.º."
            )
    elif method == "wilson":
        reasons.append(
            f"Ganó el {_num(r['win_rate'], 1)} % de sus sets. Con pocos sets ese porcentaje "
            "puede ser suerte, así que se usa una versión prudente que baja más cuantos menos "
            f"sets tiene: {_num(r['wilson'], 1)} %. Queda {rank}.º."
        )

    if r["played_events"]:
        reasons.append(
            "Torneos: "
            + _list(
                [
                    f"{e['placement']}.º de {e['entrants']} en {e['name']} ({_day(e['date'])})"
                    if e["placement"] and e["entrants"]
                    else f"{e['name']} ({_day(e['date'])})"
                    for e in r["played_events"]
                ],
                5,
            )
            + "."
        )
    beaten = _opponents(r, context, method, True)
    lost = _opponents(r, context, method, False)
    reasons.append(
        ("Mejores victorias: " + _list(beaten, 4) + ".") if beaten else "Todavía no ganó sets."
    )
    reasons.append(("Perdió con: " + _list(lost, 4) + ".") if lost else "No perdió ningún set.")
    reasons.append(
        {
            "baja": f"Todavía hay pocos datos ({r['sets']} sets): su puesto puede moverse "
            "bastante en los próximos torneos.",
            "media": "Hay datos suficientes, aunque su puesto todavía puede moverse.",
            "alta": "Tiene muchos datos: su puesto es estable.",
        }.get(r["confidence"], "")
    )
    return [x for x in reasons if x]


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
