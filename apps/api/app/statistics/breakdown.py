"""Visual statistics of one player: everything the profile charts need, in one pass.

Pure functions over rows already read from the database, so they are tested without it.
A row is one eligible set from the player's perspective (``repository.perspective``).
"""

from collections import Counter, defaultdict

from app.core.times import ASUNCION

FORM_SIZE = 10
BEST_WINS = 5
# Opponent strength bands by place in the published ranking.
TIERS = (("top10", 1, 10), ("top25", 11, 25), ("ranked", 26, None))


def _record(rows):
    wins = sum(1 for r in rows if r["won"])
    return {"wins": wins, "losses": len(rows) - wins}


def _month(at):
    return at.astimezone(ASUNCION).strftime("%Y-%m")


def _next_month(month):
    year, number = map(int, month.split("-"))
    return f"{year + number // 12}-{number % 12 + 1:02d}"


def months(rows):
    """Wins and losses per local month, with empty months filled between the first and last."""
    counts = defaultdict(lambda: {"wins": 0, "losses": 0})
    for r in rows:
        if r["completed_at"]:
            counts[_month(r["completed_at"])]["wins" if r["won"] else "losses"] += 1
    if not counts:
        return []
    result, month, last = [], min(counts), max(counts)
    while True:
        result.append({"month": month, **counts.get(month, {"wins": 0, "losses": 0})})
        if month == last:
            return result
        month = _next_month(month)


def chronological(rows):
    """Dated sets, oldest first (undated ones cannot sit in a streak or a form line)."""
    return sorted(
        (r for r in rows if r["completed_at"]), key=lambda r: (r["completed_at"], r["id"])
    )


def streaks(ordered):
    best = run = 0
    for r in ordered:
        run = run + 1 if r["won"] else 0
        best = max(best, run)
    current = {"result": None, "length": 0}
    for r in reversed(ordered):
        result = "W" if r["won"] else "L"
        if current["result"] not in (None, result):
            break
        current = {"result": result, "length": current["length"] + 1}
    return current, best


def deciding(r):
    """The set went to its last game: 2-1, 3-2… (a 1-0 is not)."""
    s, o = r["score"], r["opponent_score"]
    return s is not None and o is not None and abs(s - o) == 1 and min(s, o) >= 1


def scores(rows):
    counts = Counter(
        (r["score"], r["opponent_score"])
        for r in rows
        if r["score"] is not None
        and r["opponent_score"] is not None
        and r["score"] >= 0
        and r["opponent_score"] >= 0
    )
    return [
        {"score": s, "opponent_score": o, "sets": n}
        for (s, o), n in sorted(counts.items(), key=lambda x: (-(x[0][0] - x[0][1]), -x[0][0]))
    ]


def tier_of(place):
    if place is None:
        return "unranked"
    return next(key for key, low, high in TIERS if place >= low and (high is None or place <= high))


def breakdown(rows, placements, *, places, tags, characters):
    """``places``: {player id: ranking place}; ``tags``: {player id: tag}.

    ``places`` is empty when there is no ranking to compare with (or in doubles): then the
    strength bands and best wins are empty too.
    """
    ordered = chronological(rows)
    current, best = streaks(ordered)
    games_won = sum(r["score"] for r in rows if r["score"] and r["score"] > 0)
    games_lost = sum(
        r["opponent_score"] for r in rows if r["opponent_score"] and r["opponent_score"] > 0
    )

    def place(r):
        known = [places[p] for p in r["opponent_ids"] if p in places]
        return min(known) if known else None

    bands = []
    if places:
        grouped = defaultdict(list)
        for r in rows:
            grouped[tier_of(place(r))].append(r)
        bands = [
            {"tier": key, **_record(grouped[key])} for key in [t[0] for t in TIERS] + ["unranked"]
        ]

    beaten, seen = [], set()
    for r in sorted(
        (r for r in rows if r["won"] and place(r) is not None),
        key=lambda r: (place(r), r["completed_at"] is None, r["completed_at"]),
    ):
        key = tuple(sorted(r["opponent_ids"]))
        if key in seen:
            continue
        seen.add(key)
        beaten.append(
            {
                "opponents": [{"id": p, "tag": tags.get(p, "?")} for p in key],
                "place": place(r),
                "tournament_id": r["tournament_id"],
                "tournament_name": r["tournament_name"],
                "completed_at": r["completed_at"],
                "score": r["score"],
                "opponent_score": r["opponent_score"],
            }
        )
        if len(beaten) == BEST_WINS:
            break

    return {
        "record": _record(rows),
        "months": months(rows),
        "form": [
            {
                "result": "W" if r["won"] else "L",
                "opponents": [tags.get(p, "?") for p in sorted(r["opponent_ids"])],
                "tournament_id": r["tournament_id"],
                "tournament_name": r["tournament_name"],
                "completed_at": r["completed_at"],
                "score": r["score"],
                "opponent_score": r["opponent_score"],
            }
            for r in ordered[-FORM_SIZE:]
        ],
        "current_streak": current,
        "best_win_streak": best,
        "scores": scores(rows),
        "games": {"wins": games_won, "losses": games_lost},
        # start.gg numbers losers rounds below zero; grand finals count as winners side.
        "winners_side": _record([r for r in rows if (r["round_number"] or 0) >= 0]),
        "losers_side": _record([r for r in rows if (r["round_number"] or 0) < 0]),
        "deciding": _record([r for r in rows if deciding(r)]),
        "vs_ranking": bands,
        "best_wins": beaten,
        "placements": [
            {
                "tournament_id": p["tournament_id"],
                "tournament_name": p["tournament_name"],
                "event_name": p["event_name"],
                "starts_at": p["tournament_starts_at"],
                "placement": p["placement"],
                "entrants": p["entrants"],
            }
            for p in sorted(
                placements,
                key=lambda p: (p["tournament_starts_at"] is None, p["tournament_starts_at"]),
            )
        ],
        "characters": characters,
    }
