"""Prode scoring, ranking and achievements. Pure: no database, no start.gg (ADR-020).

The backend always computes the points; the web only shows them.
"""

from collections import Counter
from datetime import timedelta

DEFAULT_RULES = {"champion": 10, "runner_up": 7, "top8": 2}
KINDS = ("champion", "runner_up", "top8")
TOP8_PLACEMENT = 7  # double elimination: 1, 2, 3, 4, 5, 5, 7, 7


def results_from(placements):
    """{kind: start.gg player ids that make it right} from {player id: final placement}."""
    return dict(
        champion=sorted(p for p, place in placements.items() if place == 1),
        runner_up=sorted(p for p, place in placements.items() if place == 2),
        top8=sorted(p for p, place in placements.items() if place <= TOP8_PLACEMENT),
    )


def score(rules, results, picks):
    """Points of one forecaster. picks: {kind: value}; questions without a result (void)
    neither add points nor count as picks."""
    points = exact = hits = made = 0
    for kind in ("champion", "runner_up"):
        if kind in results and picks.get(kind):
            made += 1
            if picks[kind] in results[kind]:
                points += rules.get(kind, 0)
                exact += 1
                hits += 1
    if "top8" in results and picks.get("top8"):
        chosen = set(picks["top8"])
        made += len(chosen)
        right = len(chosen & set(results["top8"]))
        points += right * rules.get("top8", 0)
        hits += right
    return dict(points=points, exact_hits=exact, hits=hits, picks=made)


def rank(rows):
    """Order by points, exact hits, hits, then whoever saved first. Rows equal on all of
    them share the position (1, 2, 2, 4)."""

    def key(row):
        saved = row.get("last_saved_at")
        return (
            -row["points"],
            -row["exact_hits"],
            -row["hits"],
            saved.timestamp() if saved else float("inf"),
        )

    ordered = sorted(rows, key=key)
    for i, row in enumerate(ordered):
        same = i and key(ordered[i - 1]) == key(row)
        row["rank"] = ordered[i - 1]["rank"] if same else i + 1
    return ordered


def _achievement(kind, title, detail, rare=False):
    return dict(kind=kind, title=title, detail=detail, rare=rare)


CROWD_SHARE = 0.10  # "Contra el pueblo": the champion was picked by this share or less
CROWD_MIN = 10  # ...of at least this many forecasters
EARLY = timedelta(hours=1)
LATE = timedelta(minutes=10)


def achievements(
    contest,
    results,
    picks,
    ranked,
    *,
    players,
    seeds,
    tags,
    placements=None,
    opened_at=None,
    closes_at=None,
    first_saved=None,
    last_saved=None,
    candidates=None,
):
    """{user id: [achievement]} earned in one settled contest.

    picks: {user id: {kind: value}}; ranked: rank() rows with user_id; players: {user id:
    their start.gg player id}; seeds and tags by start.gg player id. SH-ACH-01 adds, all
    optional: placements {start.gg id: final placement}; when the contest opened and
    closed; each user's first and last saved pick; the start.gg ids that were entrants.
    """
    earned = {}

    def give(user, item):
        earned.setdefault(user, []).append(item)

    champions = set(results.get("champion") or [])
    top8 = set(results.get("top8") or [])
    champion_votes = Counter(c["champion"] for c in picks.values() if c.get("champion"))
    voters = sum(champion_votes.values())
    for user, chosen in picks.items():
        champion = chosen.get("champion")
        right = bool(champion) and champion in champions
        if right:
            seed = seeds.get(champion)
            give(
                user,
                _achievement(
                    "oracle",
                    "Oráculo",
                    f"Dijo que ganaba {tags.get(champion, champion)} en {contest}.",
                ),
            )
            if seed and seed >= 5:
                give(
                    user,
                    _achievement(
                        "upset_prophet",
                        "Profeta del batacazo",
                        f"Acertó a {tags.get(champion, champion)} campeón siendo seed {seed} en {contest}.",
                        rare=True,
                    ),
                )
            elif seed and seed > 1:
                give(
                    user,
                    _achievement(
                        "against_the_tide",
                        "Contra la corriente",
                        f"No eligió al seed 1 y acertó: {tags.get(champion, champion)} (seed {seed}) en {contest}.",
                    ),
                )
        if champion and champion == players.get(user):
            if right:
                give(
                    user,
                    _achievement(
                        "self_fulfilling",
                        "Profecía autocumplida",
                        f"Se eligió campeón a sí mismo y ganó {contest}.",
                        rare=True,
                    ),
                )
            else:
                give(
                    user,
                    _achievement(
                        "self_belief", "Fe en sí mismo", f"Se eligió campeón en {contest}."
                    ),
                )
        runner_up = chosen.get("runner_up")
        if runner_up and runner_up in set(results.get("runner_up") or []):
            give(
                user,
                _achievement("sharp_eye", "Ojo clínico", f"Acertó al subcampeón de {contest}."),
            )
        picked8 = set(chosen.get("top8") or [])
        perfect8 = len(picked8) == 8 and picked8 == top8
        if perfect8:
            give(
                user,
                _achievement(
                    "top8_seer",
                    "Vidente del Top 8",
                    f"Acertó los 8 del Top 8 de {contest}.",
                    rare=True,
                ),
            )
        if right and perfect8 and runner_up in set(results.get("runner_up") or []):
            give(
                user,
                _achievement(
                    "full_house",
                    "Pleno",
                    f"Campeón, subcampeón y Top 8 exactos en {contest}.",
                    rare=True,
                ),
            )
        # SH-ACH-01.
        right8 = len(picked8 & top8)
        if len(picked8) == 8 and right8 == 7:
            give(
                user,
                _achievement(
                    "almost_full", "Por un pelo", f"Acertó 7 de los 8 del Top 8 de {contest}."
                ),
            )
        if right and voters >= CROWD_MIN:
            share = champion_votes[champion] / voters
            if share <= CROWD_SHARE:
                give(
                    user,
                    _achievement(
                        "against_the_crowd",
                        "Contra el pueblo",
                        f"Acertó a {tags.get(champion, champion)} en {contest}: lo eligió el "
                        f"{round(100 * share)} % de los participantes.",
                        rare=True,
                    ),
                )
        if champion and placements and placements.get(champion, 0) > TOP8_PLACEMENT + 1:
            give(
                user,
                _achievement(
                    "jinx",
                    "Mufa confirmada",
                    f"Eligió campeón a {tags.get(champion, champion)} en {contest} y terminó "
                    f"{placements[champion]}.º.",
                ),
            )
        first = (first_saved or {}).get(user)
        if first and opened_at and first - opened_at <= EARLY:
            give(
                user,
                _achievement(
                    "early_bird", "Madrugador", f"Pronosticó en la primera hora de {contest}."
                ),
            )
    for row in ranked:
        if row["points"] <= 0:
            continue
        user = row["user_id"]
        last = (last_saved or {}).get(user)
        if row["rank"] <= 3 and last and closes_at and timedelta(0) <= closes_at - last <= LATE:
            give(
                user,
                _achievement(
                    "last_minute",
                    "Sobre la hora",
                    f"Cambió su pronóstico en los últimos minutos y terminó {row['rank']}.º en "
                    f"{contest}.",
                ),
            )
        mine = players.get(user)
        if row["rank"] == 1 and mine and candidates and mine in candidates:
            give(
                user,
                _achievement(
                    "double_duty",
                    "Doble función",
                    f"Jugó {contest} y ganó su Prode.",
                    rare=True,
                ),
            )
    for row in ranked:
        if row["points"] <= 0:
            continue
        if row["rank"] == 1:
            give(
                row["user_id"],
                _achievement("prode_champion", "Campeón del Prode", f"Ganó el Prode de {contest}."),
            )
        elif row["rank"] <= 3:
            give(
                row["user_id"],
                _achievement(
                    "prode_podium",
                    "Podio del Prode",
                    f"Terminó {row['rank']}.º en el Prode de {contest}.",
                ),
            )
    return earned


def _streak(flags, length=3):
    run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        if run >= length:
            return True
    return False


def lifetime(played, won, history=None):
    """Achievements across contests: {user id: [achievement]} from settled contests played
    and Prodes won per user. history (SH-ACH-01, optional): {user id: [(rank, points,
    champion hit)]} of the settled contests they played, oldest first."""
    earned = {}
    for user, rows in (history or {}).items():
        mine = earned.setdefault(user, [])
        if rows:
            mine.append(_achievement("first_prode", "Primer pronóstico", "Jugó su primer Prode."))
        if len(rows) >= 10:
            mine.append(
                _achievement("infaltable", "Infaltable", f"Jugó {len(rows)} Prodes.", rare=True)
            )
        if _streak([points > 0 and rank <= 3 for rank, points, _ in rows]):
            mine.append(
                _achievement(
                    "podium_streak",
                    "Siempre en el podio",
                    "Terminó en el podio de 3 Prodes seguidos.",
                    rare=True,
                )
            )
        if _streak([hit for _, _, hit in rows]):
            mine.append(
                _achievement("paje", "Paje", "Acertó al campeón en 3 Prodes seguidos.", rare=True)
            )
    for user, count in played.items():
        if count >= 3:
            earned.setdefault(user, []).append(
                _achievement("regular", "Habitué del Prode", f"Jugó {count} Prodes.")
            )
    for user, count in won.items():
        if count >= 2:
            earned.setdefault(user, []).append(
                _achievement("dynasty", "Dinastía", f"Ganó {count} Prodes.", rare=True)
            )
    return earned
