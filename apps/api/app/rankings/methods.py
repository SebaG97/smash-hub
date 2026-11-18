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


def bradley_terry(games, *, prior=1.0, iterations=1000, tolerance=1e-5, weights=None):
    """Bradley-Terry strengths by Hunter's MM algorithm, order independent.

    Each player also gets ``prior`` virtual wins and losses against a fixed reference of
    strength 1, which keeps unbeaten or isolated players finite. Returned on an Elo-like
    scale: 1500 + 400*log10(strength), so the reference player is 1500.
    ``weights`` ({game id: weight}) scales each set; missing ids weigh 1.
    """
    weights = weights or {}
    wins = defaultdict(float)
    meetings = defaultdict(lambda: defaultdict(float))
    for g in sorted(games, key=lambda g: (g["completed_at"], str(g["id"]))):
        a, b, a_won = g["players_a"][0], g["players_b"][0], bool(g["a_won"])
        w = weights.get(g["id"], 1.0)
        if w <= 0:
            continue
        wins[a if a_won else b] += w
        meetings[a][b] += w
        meetings[b][a] += w
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


def set_weights(games, *, end, half_life_days=90.0, online_weight=0.01):
    """Weight of each set for ``weighted_bradley_terry``, {game id: weight}.

    - age: halves every ``half_life_days`` before ``end``, so old sets fade instead of
      dropping off a window edge;
    - online: ``online_weight`` times an offline set (games carry ``online``);
    - repeated pairs: each set of a pair that met n times weighs 1/sqrt(n), so the whole
      head-to-head counts like sqrt(n) sets and a weekly local rival does not outweigh
      everyone else. Order independent: every set of the pair gets the same factor.
    """
    pairs = defaultdict(int)
    for g in games:
        pairs[frozenset((g["players_a"][0], g["players_b"][0]))] += 1
    weights = {}
    for g in games:
        age = max((end - g["completed_at"]).total_seconds() / 86400, 0.0)
        w = 0.5 ** (age / half_life_days) if half_life_days else 1.0
        if g.get("online"):
            w *= online_weight
        w /= math.sqrt(pairs[frozenset((g["players_a"][0], g["players_b"][0]))])
        weights[g["id"]] = w
    return weights


def weighted_bradley_terry(
    games, *, end, half_life_days=90.0, online_weight=0.01, prior=1.0, **kwargs
):
    """Bradley-Terry over weighted sets (see ``set_weights``).

    The ``prior`` virtual games against the 1500 reference do not fade, so a player whose
    sets are few, old or online gets pulled toward 1500: little recent evidence, little
    distance from the average.
    """
    weights = set_weights(
        games, end=end, half_life_days=half_life_days, online_weight=online_weight
    )
    return bradley_terry(games, prior=prior, weights=weights, **kwargs)


def elo_probability(rating_a, rating_b):
    """P(A beats B) on the Elo scale; exact for Elo and for Bradley-Terry as returned here."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def glicko_probability(rating_a, rd_a, rating_b, rd_b):
    """P(A beats B) from two Glicko ratings, discounting by both uncertainties."""
    q = math.log(10) / 400
    g = 1 / math.sqrt(1 + 3 * q * q * (rd_a * rd_a + rd_b * rd_b) / math.pi**2)
    return 1 / (1 + 10 ** (-g * (rating_a - rating_b) / 400))


def wilson_lower_bound(wins, losses, *, z=1.96):
    """Lower bound of the 95% Wilson interval of the win rate, in percent."""
    n = wins + losses
    if n == 0:
        return None
    phat = wins / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return 100 * (centre - margin) / (1 + z * z / n)


def glicko1(games, *, initial=1500.0, initial_rd=350.0, min_rd=30.0, c=34.0, period_days=7):
    """Glicko (Glickman 1999) with weekly rating periods.

    ``c`` grows RD while a player is inactive (about 50 -> 350 in two years).
    Returns {player: (rating, rd)}.
    """
    q = math.log(10) / 400

    def g(rd):
        return 1 / math.sqrt(1 + 3 * q * q * rd * rd / math.pi**2)

    periods = defaultdict(list)
    for a, b, a_won, at in (
        (x["players_a"][0], x["players_b"][0], bool(x["a_won"]), x["completed_at"])
        for x in sorted(games, key=lambda x: (x["completed_at"], str(x["id"])))
    ):
        periods[at.toordinal() // period_days].append((a, b, a_won))
    rating, rd, last = {}, {}, {}
    for period in sorted(periods):
        matches = defaultdict(list)
        for a, b, a_won in periods[period]:
            matches[a].append((b, 1.0 if a_won else 0.0))
            matches[b].append((a, 0.0 if a_won else 1.0))
        before = {}
        for p in matches:
            r0, d0 = rating.get(p, initial), rd.get(p, initial_rd)
            if p in last:
                d0 = min(math.sqrt(d0 * d0 + c * c * (period - last[p])), initial_rd)
            before[p] = (r0, d0)
        for p, results in matches.items():
            r0, d0 = before[p]
            terms = []
            for opponent, score in results:
                ro, do = before.get(opponent, (initial, initial_rd))
                expected = 1 / (1 + 10 ** (-g(do) * (r0 - ro) / 400))
                terms.append((g(do), expected, score))
            d2 = 1 / (q * q * sum(w * w * e * (1 - e) for w, e, _ in terms))
            denominator = 1 / (d0 * d0) + 1 / d2
            rating[p] = r0 + q / denominator * sum(w * (s - e) for w, e, s in terms)
            rd[p] = max(math.sqrt(1 / denominator), min_rd)
            last[p] = period
    return {p: (rating[p], rd[p]) for p in rating}
