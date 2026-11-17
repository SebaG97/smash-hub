"""Data of the social media images of one tournament (SH-SOCIAL-01).

Each key of `story()` feeds one image: podium, champion's path, grand final, upsets,
seed performance, closest sets, numbers, characters, newcomers and returns, and a
rivalry. Results are what happened in the bracket, guests of another country included
(ADR-024); only debuts and rivalries, which are about the scene, count locals alone.
What needs the database (ranking impact, achievements, Prode) is read by the router.
"""

from collections import Counter, defaultdict
from datetime import timedelta

from app.insights.engine import tier, tournament_summary, unique_upsets

RETURN_DAYS = 180  # away this long counts as a return
LIMIT = 6


def _who(data, player, seed=None):
    item = dict(id=str(player), tag=data.tags.get(player))
    if seed is not None:
        item["seed"] = seed
    return item


def _score(m, perspective=None):
    """ "3-1" from the winner's side, or from `perspective`'s side when given."""
    if not m.score:
        return None
    w, lo = m.score
    return f"{lo}-{w}" if perspective is not None and perspective == m.loser else f"{w}-{lo}"


def _set(data, m):
    return dict(
        winner=_who(data, m.winner, m.winner_seed),
        loser=_who(data, m.loser, m.loser_seed),
        score=_score(m),
        round=m.round,
        factor=m.factor,
        comeback=m.comeback,
        games=[g for g in m.games if g["winner"] or g["loser"]],
    )


def _full_length(m):
    """The loser took all but one of the games needed: the set went to the last game."""
    if not m.score:
        return False
    w, lo = m.score
    return w >= 2 and lo == w - 1


def _grand_finals(matches):
    finals = [m for m in matches if "grand final" in (m.round or "").lower()]
    return sorted(finals, key=lambda m: (m.at, m.id))


def champion_path(data, matches, champion):
    sets = sorted((m for m in matches if champion in (m.winner, m.loser)), key=lambda m: m.at)
    path = []
    for m in sets:
        rival = m.loser if m.winner == champion else m.winner
        seed = m.loser_seed if m.winner == champion else m.winner_seed
        path.append(
            dict(
                opponent=_who(data, rival, seed),
                won=m.winner == champion,
                score=_score(m, champion),
                round=m.round,
                losers=(m.round_number or 0) < 0,
                factor=m.factor if m.winner == champion else 0,
            )
        )
    return path


def seed_performance(event):
    seeded = [f for f in event if f["seed"]]
    delta = {id(f): tier(f["seed"]) - tier(f["placement"]) for f in seeded}
    over = sorted(
        (f for f in seeded if delta[id(f)] > 0), key=lambda f: (-delta[id(f)], f["placement"])
    )
    under = sorted((f for f in seeded if delta[id(f)] < 0), key=lambda f: (delta[id(f)], f["seed"]))
    return over, under, delta


def numbers(matches, entrants, upsets):
    scored = [m for m in matches if m.score]
    characters = Counter(
        c for m in matches for g in m.games for c in (g["winner"], g["loser"]) if _real(c)
    )
    biggest = max((m.factor for m in matches), default=0)
    return dict(
        entrants=entrants,
        sets=len(matches),
        games=sum(sum(m.score) for m in scored),
        full_length=sum(1 for m in matches if _full_length(m)),
        sweeps=sum(1 for m in scored if m.score[1] == 0 and m.score[0] >= 2),
        comebacks=sum(1 for m in matches if m.comeback),
        upsets=len(upsets),
        biggest_upset=biggest,
        characters=len(characters),
        top_character=characters.most_common(1)[0][0] if characters else None,
    )


def _real(character):
    return bool(character) and character != "Random Character"


def characters(data, matches):
    games, wins, players = Counter(), Counter(), defaultdict(set)
    reported = 0
    for m in matches:
        for g in m.games:
            if not (_real(g["winner"]) and _real(g["loser"])) or g["won"] is None:
                continue
            reported += 1
            for side, player in (("winner", m.winner), ("loser", m.loser)):
                c = g[side]
                games[c] += 1
                players[c].add(player)
                if g["won"] == (side == "winner"):
                    wins[c] += 1
    total = sum(sum(m.score) for m in matches if m.score)
    return dict(
        games=reported,
        coverage=round(100 * reported / total) if total else None,
        items=[
            dict(
                character=c,
                games=n,
                share=round(100 * n / (2 * reported), 1),
                win_rate=round(100 * wins[c] / n),
                players=len(players[c]),
            )
            for c, n in sorted(games.items(), key=lambda x: (-x[1], x[0]))[:8]
        ],
    )


def newcomers(data, event, tournament_id):
    """Locals who played their first tournament here, and those back after months away."""
    starts = {f["tournament_id"]: f["starts_at"] for f in data.finishes}
    here = starts.get(str(tournament_id))
    debuts, returns = [], []
    for f in event:
        player = f["player"]
        if not data.local(player) or here is None:
            continue
        before = [
            g["starts_at"]
            for g in data.finishes
            if g["player"] == player
            and g["tournament_id"] != str(tournament_id)
            and g["starts_at"]
            and g["starts_at"] < here
        ]
        row = dict(**_who(data, player), placement=f["placement"], seed=f["seed"])
        if not before:
            debuts.append(row)
        elif here - max(before) >= timedelta(days=RETURN_DAYS):
            returns.append(dict(**row, days=(here - max(before)).days))
    debuts.sort(key=lambda r: r["placement"])
    returns.sort(key=lambda r: r["placement"])
    return dict(debuts=debuts[:8], debut_count=len(debuts), returns=returns[:LIMIT])


def rivalries(data, matches):
    """The pairs of locals with the longest history who met here: their record before
    this tournament, what happened here and the record after it."""
    if not matches:
        return []
    first = min(m.at for m in matches)
    ids = {m.id for m in matches}
    here = defaultdict(list)
    for m in matches:
        if data.local(m.winner) and data.local(m.loser):
            here[frozenset((m.winner, m.loser))].append(m)
    history = Counter()
    for m in data.matches:
        if m.at < first and m.id not in ids:
            history[(m.winner, m.loser)] += 1
    rows = []
    for pair, sets in here.items():
        a, b = sorted(pair, key=lambda p: (data.tags.get(p) or "", str(p)))
        before = (history[(a, b)], history[(b, a)])
        if sum(before) < 2:
            continue
        won = (sum(m.winner == a for m in sets), sum(m.winner == b for m in sets))
        rows.append(
            dict(
                a=_who(data, a),
                b=_who(data, b),
                before=list(before),
                here=[_set(data, m) for m in sorted(sets, key=lambda m: m.at)],
                after=[before[0] + won[0], before[1] + won[1]],
            )
        )
    rows.sort(key=lambda r: -sum(r["before"]))
    return rows[:3]


def story(data, tournament_id, event_id=None):
    summary = tournament_summary(data, tournament_id, limit=8, event_id=event_id)
    if summary is None:
        return None
    chosen = summary["event_id"]
    matches = [m for m in data.matches if m.event_id == chosen]
    event = sorted(
        (f for f in data.finishes if f["event_id"] == chosen),
        key=lambda f: (f["placement"], f["seed"] or 9999),
    )
    champion = event[0]["player"] if event and event[0]["placement"] == 1 else None
    upsets = unique_upsets(matches)
    over, under, delta = seed_performance(event)
    close = sorted(
        (m for m in matches if _full_length(m)),
        key=lambda m: (-m.score[0], -abs(m.round_number or 0), -m.at.timestamp()),
    )
    finals = _grand_finals(matches)

    def performer(f):
        return dict(
            **_who(data, f["player"]),
            seed=f["seed"],
            placement=f["placement"],
            tiers=delta[id(f)],
        )

    return dict(
        summary=summary,
        champion=_who(data, champion) if champion else None,
        champion_path=champion_path(data, matches, champion) if champion else [],
        grand_final=[_set(data, m) for m in finals],
        upsets=[_set(data, m) for m in upsets[:LIMIT]],
        over=[performer(f) for f in over[:LIMIT]],
        under=[performer(f) for f in under[:LIMIT]],
        close_sets=[_set(data, m) for m in close[:LIMIT]],
        numbers=numbers(matches, summary["entrants"], upsets),
        characters=characters(data, matches),
        newcomers=newcomers(data, event, tournament_id),
        rivalries=rivalries(data, matches),
    )
