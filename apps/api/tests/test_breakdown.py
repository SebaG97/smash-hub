"""Profile charts computed from a player's sets (no database needed)."""

from datetime import UTC, datetime
from uuid import uuid4

from app.statistics.breakdown import breakdown, deciding, months, streaks, tier_of

T = uuid4()
A, B, C, D = (uuid4() for _ in range(4))


def row(day, won, opponent, score=None, opponent_score=None, round_number=1, month=3):
    return {
        "id": uuid4(),
        "completed_at": datetime(2026, month, day, 20, tzinfo=UTC) if day else None,
        "won": won,
        "opponent_ids": [opponent],
        "score": score,
        "opponent_score": opponent_score,
        "round_number": round_number,
        "tournament_id": T,
        "tournament_name": "Open",
    }


def test_months_fill_gaps_in_local_time():
    rows = [row(1, True, A, month=1), row(2, False, B, month=3)]
    # 1 March 20:00 UTC is still 1 March in Asunción; February has no sets but is shown.
    assert months(rows) == [
        {"month": "2026-01", "wins": 1, "losses": 0},
        {"month": "2026-02", "wins": 0, "losses": 0},
        {"month": "2026-03", "wins": 0, "losses": 1},
    ]
    assert months([row(None, True, A)]) == []


def test_streaks_current_and_best():
    ordered = [row(d, w, A) for d, w in enumerate([True, True, True, False, True, True], 1)]
    assert streaks(ordered) == ({"result": "W", "length": 2}, 3)
    assert streaks([]) == ({"result": None, "length": 0}, 0)


def test_deciding_game_and_tiers():
    assert deciding(row(1, True, A, 2, 1)) and deciding(row(1, False, A, 2, 3))
    assert not deciding(row(1, True, A, 1, 0)) and not deciding(row(1, True, A))
    assert [tier_of(p) for p in (1, 10, 11, 25, 26, None)] == [
        "top10",
        "top10",
        "top25",
        "top25",
        "ranked",
        "unranked",
    ]


def test_breakdown_bands_best_wins_and_sides():
    rows = [
        row(1, True, A, 2, 1),
        row(2, True, A, 2, 0),  # same rival again: listed once among best wins
        row(3, False, B, 0, 2, round_number=-2),
        row(4, True, C, 2, 0, round_number=-3),
        row(5, True, D, -1, 0),  # DQ-like scores never count as games
    ]
    result = breakdown(
        rows,
        [],
        places={A: 3, B: 12, C: 40},
        tags={A: "Ace", B: "Bee", C: "Cid", D: "Dot"},
        characters=[],
    )
    assert result["record"] == {"wins": 4, "losses": 1}
    assert result["vs_ranking"] == [
        {"tier": "top10", "wins": 2, "losses": 0},
        {"tier": "top25", "wins": 0, "losses": 1},
        {"tier": "ranked", "wins": 1, "losses": 0},
        {"tier": "unranked", "wins": 1, "losses": 0},
    ]
    assert [(w["opponents"][0]["tag"], w["place"]) for w in result["best_wins"]] == [
        ("Ace", 3),
        ("Cid", 40),
    ]
    assert result["winners_side"] == {"wins": 3, "losses": 0}
    assert result["losers_side"] == {"wins": 1, "losses": 1}
    assert result["deciding"] == {"wins": 1, "losses": 0}
    assert result["games"] == {"wins": 6, "losses": 3}
    assert result["scores"][0] == {"score": 2, "opponent_score": 0, "sets": 2}
    assert [f["opponents"] for f in result["form"]] == [["Ace"], ["Ace"], ["Bee"], ["Cid"], ["Dot"]]
    assert result["current_streak"] == {"result": "W", "length": 2}


def test_breakdown_without_ranking():
    result = breakdown([row(1, True, A)], [], places={}, tags={}, characters=[])
    assert result["vs_ranking"] == [] and result["best_wins"] == []
