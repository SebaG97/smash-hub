"""How well each head-to-head method predicts sets it has not seen (backtest).

For every offline event in the test range, each method is trained only with the sets
played before that event started and then predicts every set of the event between two
players it already knows. Pure: no database, no network.

Metrics, lower is better for log loss and higher for accuracy:
- log_loss: mean of -ln(probability given to the actual winner), i.e. cross-entropy.
  A coin flip scores ln 2 = 0.693; it punishes confident misses hard.
- accuracy: % of sets the method's favourite won (a 50/50 call counts half).
"""

import math
from collections import defaultdict
from datetime import timedelta

from app.rankings.methods import (
    bradley_terry,
    elo,
    elo_probability,
    glicko1,
    glicko_probability,
    weighted_bradley_terry,
)
from app.rankings.policy import Policy, period_start, utc
from app.rankings.service import calculate

EVALUATED = ("glicko2", "glicko1", "elo", "bradley_terry", "weighted_bt")
COIN_FLIP = math.log(2)


def games_from(sets, *, merges, duplicates, window_start, window_end):
    """Counted sets inside the window as engine games, with merged identities applied."""

    def canon(pid):
        pid = merges.get(pid, pid) if pid else pid
        return duplicates.get(pid, pid) if pid else pid

    start, end = utc(window_start), utc(window_end)
    games = []
    for s in sets:
        at = utc(s["played_at"])
        a, b = canon(s["p1_player_id"]), canon(s["p2_player_id"])
        if not start <= at < end or not s["counted"] or not a or not b or a == b:
            continue
        games.append(
            dict(
                id=s["startgg_set_id"],
                completed_at=at,
                players_a=[a],
                players_b=[b],
                a_won=canon(s["winner_player_id"]) == a,
                online=bool(s["online"]),
                event_id=s["startgg_event_id"],
                event_name=s.get("tournament_name"),
            )
        )
    return games


def _predictors(train, at, parameters):
    """{method: f(a, b) -> P(a beats b) or None when a player is unknown}."""
    policy = Policy()
    computed = calculate(train, policy, period_start(at, policy))
    g2 = {r["player_id"]: (r["rating"], r["rd"]) for r in computed[-1][2]} if computed else {}
    g1 = glicko1(train)
    el = elo(train, k=parameters.elo_k) if train else {}
    bt = bradley_terry(train)
    wbt = weighted_bradley_terry(
        train,
        end=at,
        half_life_days=parameters.half_life_days,
        online_weight=parameters.online_weight,
    )

    def glicko(table):
        return lambda a, b: (
            glicko_probability(*table[a], *table[b]) if a in table and b in table else None
        )

    def scale(table):
        return lambda a, b: (
            elo_probability(table[a], table[b]) if a in table and b in table else None
        )

    return dict(
        glicko2=glicko(g2),
        glicko1=glicko(g1),
        elo=scale(el),
        bradley_terry=scale(bt),
        weighted_bt=scale(wbt),
    )


def backtest(games, parameters, *, test_from, min_sets=1):
    """Predict every offline event that starts on or after ``test_from``.

    Only sets between two players who both had at least ``min_sets`` earlier sets are
    scored, and every method scores the same sets, so the numbers are comparable.
    """
    test_from = utc(test_from)
    events = defaultdict(list)
    for g in games:
        if not g["online"]:
            events[g["event_id"]].append(g)
    tested = sorted(
        (min(x["completed_at"] for x in sets), event_id, sets)
        for event_id, sets in events.items()
        if min(x["completed_at"] for x in sets) >= test_from
    )
    totals = {m: dict(loss=0.0, hits=0.0) for m in EVALUATED}
    per_event, scored = [], 0
    for at, event_id, sets in tested:
        train = [g for g in games if g["completed_at"] < at]
        if not train:
            continue
        seen = defaultdict(int)
        for g in train:
            seen[g["players_a"][0]] += 1
            seen[g["players_b"][0]] += 1
        predict = _predictors(train, at, parameters)
        event = {m: dict(loss=0.0, hits=0.0) for m in EVALUATED}
        n = 0
        for g in sets:
            a, b = g["players_a"][0], g["players_b"][0]
            if seen[a] < min_sets or seen[b] < min_sets:
                continue
            winner, loser = (a, b) if g["a_won"] else (b, a)
            probabilities = {m: predict[m](winner, loser) for m in EVALUATED}
            if any(p is None for p in probabilities.values()):
                continue
            n += 1
            for m, p in probabilities.items():
                p = min(max(p, 1e-6), 1 - 1e-6)
                event[m]["loss"] -= math.log(p)
                event[m]["hits"] += 1.0 if p > 0.5 else 0.5 if p == 0.5 else 0.0
        if not n:
            continue
        scored += n
        for m in EVALUATED:
            totals[m]["loss"] += event[m]["loss"]
            totals[m]["hits"] += event[m]["hits"]
        per_event.append(
            dict(
                event_id=event_id,
                name=sets[0].get("event_name"),
                date=at.date().isoformat(),
                sets=n,
                log_loss={m: round(event[m]["loss"] / n, 4) for m in EVALUATED},
            )
        )
    methods = [
        dict(
            method=m,
            log_loss=round(totals[m]["loss"] / scored, 4) if scored else None,
            accuracy=round(100 * totals[m]["hits"] / scored, 1) if scored else None,
        )
        for m in EVALUATED
    ]
    methods.sort(key=lambda r: (r["log_loss"] is None, r["log_loss"] or 0, r["method"]))
    return dict(
        sets=scored,
        events=len(per_event),
        coin_flip=round(COIN_FLIP, 4),
        methods=methods,
        per_event=per_event,
    )


def default_test_from(window_start, window_end, warmup_days=120):
    """Leave the first ``warmup_days`` (at most half the window) for training only."""
    start, end = utc(window_start), utc(window_end)
    return start + min(timedelta(days=warmup_days), (end - start) / 2)
