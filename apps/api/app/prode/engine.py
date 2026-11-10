"""Prode scoring, ranking and achievements. Pure: no database, no start.gg (ADR-020).

The backend always computes the points; the web only shows them.
"""

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


def achievements(contest, results, picks, ranked, *, players, seeds, tags):
    """{user id: [achievement]} earned in one settled contest.

    picks: {user id: {kind: value}}; ranked: rank() rows with user_id; players: {user id:
    their start.gg player id}; seeds and tags by start.gg player id.
    """
    earned = {}

    def give(user, item):
        earned.setdefault(user, []).append(item)

    champions = set(results.get("champion") or [])
    top8 = set(results.get("top8") or [])
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


def lifetime(played, won):
    """Achievements across contests: {user id: [achievement]} from settled contests played
    and Prodes won per user."""
    earned = {}
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
