"""Alternative strength methods over the same set list, for comparison with Glicko-2.

Every function is pure and deterministic. Input games are dicts with ``id``,
``completed_at``, ``players_a``/``players_b`` (one player each) and ``a_won``.
"""

import math
from collections import defaultdict


def _pairs(games):
    return [
        (g["players_a"][0], g["players_b"][0], bool(g["a_won"]))
        for g in sorted(games, key=lambda g: (g["completed_at"], str(g["id"])))
    ]


def elo(games, *, k=32.0, initial=1500.0):
    """Classic Elo, applied set by set in chronological order."""
    ratings = defaultdict(lambda: initial)
    for a, b, a_won in _pairs(games):
        expected = 1 / (1 + 10 ** ((ratings[b] - ratings[a]) / 400))
        delta = k * ((1.0 if a_won else 0.0) - expected)
        ratings[a] += delta
        ratings[b] -= delta
    return dict(ratings)


def bradley_terry(games, *, prior=1.0, iterations=1000, tolerance=1e-5):
    """Bradley-Terry strengths by Hunter's MM algorithm, order independent.

    Each player also gets ``prior`` virtual wins and losses against a fixed reference of
    strength 1, which keeps unbeaten or isolated players finite. Returned on an Elo-like
    scale: 1500 + 400*log10(strength), so the reference player is 1500.
    """
    wins = defaultdict(float)
    meetings = defaultdict(lambda: defaultdict(float))
    for a, b, a_won in _pairs(games):
        wins[a if a_won else b] += 1
        meetings[a][b] += 1
        meetings[b][a] += 1
    players = sorted(meetings)
    index = {p: i for i, p in enumerate(players)}
    neighbours = [[(index[q], n) for q, n in meetings[p].items()] for p in players]
    numerators = [wins[p] + prior for p in players]
    gamma = [1.0] * len(players)
    for _ in range(iterations):
        # Gauss-Seidel: reuse strengths updated in this sweep, which converges faster.
        change = 0.0
        for i, edges in enumerate(neighbours):
            g = gamma[i]
            denominator = 2 * prior / (g + 1)
            for j, n in edges:
                denominator += n / (g + gamma[j])
            new = numerators[i] / denominator
            change = max(change, abs(math.log(new / g)))
            gamma[i] = new
        if change < tolerance:
            break
    return {p: 1500 + 400 * math.log10(gamma[i]) for p, i in index.items()}


def wilson_lower_bound(wins, losses, *, z=1.96):
    """Lower bound of the 95% Wilson interval of the win rate, in percent."""
    n = wins + losses
    if n == 0:
        return None
    phat = wins / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return 100 * (centre - margin) / (1 + z * z / n)
