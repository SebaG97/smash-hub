"""Alternative strength methods (Mission 05.1)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.rankings.methods import bradley_terry, elo, wilson_lower_bound

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def game(n, winner, loser, day=0):
    return dict(
        id=str(n),
        completed_at=T0 + timedelta(days=day),
        players_a=[winner],
        players_b=[loser],
        a_won=True,
    )


def test_elo_is_zero_sum_and_rewards_upsets_more():
    ratings = elo([game(1, "a", "b")], k=32)
    assert ratings == {"a": 1516, "b": 1484}
    upset = elo([game(1, "a", "b"), game(2, "c", "a", day=1)], k=32)
    assert upset["c"] - 1500 > 16
    assert sum(upset.values()) == pytest.approx(4500)


def test_bradley_terry_orders_a_chain_and_ignores_order():
    games = [
        game(i, w, lo, day=i) for i, (w, lo) in enumerate([("a", "b"), ("b", "c"), ("a", "c")] * 3)
    ]
    strengths = bradley_terry(games)
    assert strengths["a"] > strengths["b"] > strengths["c"]
    assert bradley_terry(list(reversed(games))) == pytest.approx(strengths)
    # An unbeaten player stays finite thanks to the virtual reference games.
    assert bradley_terry([game(1, "x", "y")])["x"] < 3000


def test_wilson_penalizes_small_samples():
    assert wilson_lower_bound(0, 0) is None
    assert wilson_lower_bound(7, 3) < wilson_lower_bound(70, 30) < 70
    assert wilson_lower_bound(10, 0) < 100
