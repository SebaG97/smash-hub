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


def test_glicko1_rewards_wins_and_shrinks_uncertainty():
    from app.rankings.methods import glicko1

    games = [game(i, "a", "b", day=i * 7) for i in range(6)]
    ratings = glicko1(games)
    assert ratings["a"][0] > 1500 > ratings["b"][0]
    assert ratings["a"][1] < 350


def test_weighted_bradley_terry_fades_old_sets_and_online():
    from app.rankings.methods import set_weights, weighted_bradley_terry

    end = T0 + timedelta(days=180)
    # b beat a long ago; a beat b recently: recent evidence wins.
    games = [game(1, "b", "a", day=0), game(2, "a", "b", day=180)]
    ratings = weighted_bradley_terry(games, end=end)
    assert ratings["a"] > ratings["b"]
    weights = set_weights(games, end=end)
    # 180 days = two half-lives, and the pair met twice: 1/sqrt(2) each.
    assert weights["1"] == pytest.approx(0.25 / 2**0.5)
    assert weights["2"] == pytest.approx(1 / 2**0.5)
    online = dict(game(3, "c", "d", day=180), online=True)
    assert set_weights([online], end=end)["3"] == pytest.approx(0.01)
    # Unweighted Bradley-Terry sees the same 1-1 record as a tie.
    plain = bradley_terry(games)
    assert plain["a"] == pytest.approx(plain["b"])


def test_repeated_rival_counts_less_than_many_rivals():
    from app.rankings.methods import weighted_bradley_terry

    end = T0 + timedelta(days=1)
    farmer = [game(i, "f", "local", day=0) for i in range(8)]
    traveller = [game(10 + i, "t", f"r{i}", day=0) for i in range(8)]
    ratings = weighted_bradley_terry(farmer + traveller, end=end)
    assert ratings["t"] > ratings["f"]


def test_backtest_scores_every_method_on_the_same_sets():
    from app.seeding.engine import Parameters
    from app.seeding.evaluation import EVALUATED, backtest

    def event_games(event, day, results):
        return [
            dict(game(f"{event}-{i}", w, lo, day=day), online=False, event_id=event)
            for i, (w, lo) in enumerate(results)
        ]

    ladder = [("a", "b"), ("b", "c"), ("a", "c"), ("c", "d"), ("b", "d")]
    games = []
    for week in range(10):
        games += event_games(f"e{week}", week * 7, ladder)
    report = backtest(games, Parameters(), test_from=T0 + timedelta(days=35))
    assert report["events"] == 5 and report["sets"] == 25
    assert {m["method"] for m in report["methods"]} == set(EVALUATED)
    for m in report["methods"]:
        # A perfectly stable ladder: every method should beat a coin flip.
        assert m["log_loss"] < report["coin_flip"]
        assert m["accuracy"] == 100.0
