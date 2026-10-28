"""Records, upsets, streaks, comebacks and badges from imported singles results (Mission 13).

Everything is computed in memory from one query over eligible singles sets of published
tournaments: the community's volume (a few thousand sets) makes that cheaper and simpler
than per-question SQL, and the result is cached per process for a few minutes.
"""

import bisect
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select

from app.competitions.models import (
    EntrantMember,
    Event,
    EventEntrant,
    Set,
    SetSelection,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.players.models import Player

# Placements a double-elimination bracket can produce; seeds map onto the same tiers.
TIERS = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025]
CACHE_SECONDS = 300


def tier(seed_or_place):
    return bisect.bisect_right(TIERS, seed_or_place) - 1


def upset_factor(winner_seed, loser_seed):
    """start.gg's idea: how many placement tiers apart the winner was expected to finish."""
    if not winner_seed or not loser_seed:
        return 0
    return max(tier(winner_seed) - tier(loser_seed), 0)


@dataclass
class Match:
    id: str
    at: object
    tournament_id: str
    tournament: str
    event_id: str
    round: str | None
    winner: str
    loser: str
    winner_seed: int | None
    loser_seed: int | None
    comeback: bool

    @property
    def factor(self):
        return upset_factor(self.winner_seed, self.loser_seed)


@dataclass
class Data:
    matches: list = field(default_factory=list)
    tags: dict = field(default_factory=dict)
    finishes: list = field(default_factory=list)  # (player, placement, entrants, tournament...)
    picks: dict = field(default_factory=dict)  # player -> Counter(character -> games)
    games: list = field(default_factory=list)  # Game of eligible singles sets


@dataclass
class Game:
    """One game with both characters known: (player, character) per side and the winner."""

    a: tuple
    b: tuple
    winner: object


def load(session):
    member = (
        select(EntrantMember.entrant_id, TournamentParticipant.player_id)
        .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .subquery()
    )
    entrant_player = dict(session.execute(select(member.c.entrant_id, member.c.player_id)).all())
    singles = (
        select(Event.id, Tournament.id, Tournament.name, Tournament.starts_at, Event.num_entrants)
        .join(Tournament, Tournament.id == Event.tournament_id)
        .where(Tournament.published.is_(True), Event.team_size == 1)
    )
    events = {e: (t, name, starts, n) for e, t, name, starts, n in session.execute(singles)}
    entrants = {
        e_id: (event_id, seed, place)
        for e_id, event_id, seed, place in session.execute(
            select(
                EventEntrant.id, EventEntrant.event_id, EventEntrant.seed, EventEntrant.placement
            ).where(EventEntrant.event_id.in_(list(events)))
        )
    }
    sides = defaultdict(list)
    for set_id, entrant_id, won in session.execute(
        select(SetSide.set_id, SetSide.entrant_id, SetSide.is_winner).where(
            SetSide.event_id.in_(list(events)), SetSide.entrant_id.is_not(None)
        )
    ):
        sides[set_id].append((entrant_id, won))
    games = defaultdict(dict)  # set -> game number -> winning entrant
    picks = defaultdict(Counter)
    selections = defaultdict(list)  # (set, game number) -> [(entrant, character)]
    from app.games.models import Character

    for set_id, number, entrant_id, won, character in session.execute(
        select(
            SetSelection.set_id,
            SetSelection.game_number,
            SetSelection.entrant_id,
            SetSelection.won,
            Character.name,
        )
        .join(Character, Character.id == SetSelection.character_id)
        .where(SetSelection.event_id.in_(list(events)))
    ):
        if won:
            games[set_id][number] = entrant_id
        selections[(set_id, number)].append((entrant_id, character))
        player = entrant_player.get(entrant_id)
        if player and character != "Random Character":
            picks[player][character] += 1

    data = Data(picks=dict(picks))
    data.tags = dict(session.execute(select(Player.id, Player.tag)).all())
    for set_id, event_id, at, round_label in session.execute(
        select(Set.id, Set.event_id, Set.completed_at, Set.round_label).where(
            Set.event_id.in_(list(events)), Set.stats_eligible.is_(True)
        )
    ):
        pair = sides.get(set_id) or []
        winners = [e for e, won in pair if won]
        losers = [e for e, won in pair if not won]
        if len(winners) != 1 or len(losers) != 1 or at is None:
            continue
        w, lo = winners[0], losers[0]
        pw, pl = entrant_player.get(w), entrant_player.get(lo)
        if not pw or not pl:
            continue
        tournament_id, name, _, _ = events[event_id]
        first = games.get(set_id, {}).get(1)
        data.matches.append(
            Match(
                id=str(set_id),
                at=at,
                tournament_id=str(tournament_id),
                tournament=name,
                event_id=str(event_id),
                round=round_label,
                winner=pw,
                loser=pl,
                winner_seed=entrants.get(w, (None, None, None))[1],
                loser_seed=entrants.get(lo, (None, None, None))[1],
                comeback=first is not None and first == lo,
            )
        )
    data.matches.sort(key=lambda m: (m.at, m.id))
    eligible = {m.id for m in data.matches}
    for (set_id, number), sides_picked in selections.items():
        if str(set_id) not in eligible or len(sides_picked) != 2:
            continue
        (ea, ca), (eb, cb) = sides_picked
        pa, pb = entrant_player.get(ea), entrant_player.get(eb)
        winner = games.get(set_id, {}).get(number)
        if not pa or not pb or winner not in (ea, eb) or "Random Character" in (ca, cb):
            continue
        data.games.append(Game(a=(pa, ca), b=(pb, cb), winner=entrant_player[winner]))
    for entrant_id, (event_id, seed, place) in entrants.items():
        player = entrant_player.get(entrant_id)
        tournament_id, name, starts, size = events[event_id]
        if player and place:
            data.finishes.append(
                dict(
                    player=player,
                    placement=place,
                    seed=seed,
                    entrants=size,
                    tournament_id=str(tournament_id),
                    tournament=name,
                    event_id=str(event_id),
                    starts_at=starts,
                )
            )
    return data


_cache = {"at": 0.0, "data": None}
_lock = threading.Lock()


def cached(session):
    with _lock:
        if _cache["data"] is None or time.monotonic() - _cache["at"] > CACHE_SECONDS:
            _cache["data"], _cache["at"] = load(session), time.monotonic()
        return _cache["data"]


def invalidate():
    with _lock:
        _cache["data"] = None


# ---------------------------------------------------------------- per player


def streaks(matches, player):
    best = current = 0
    best_end = None
    for m in matches:
        if player not in (m.winner, m.loser):
            continue
        if m.winner == player:
            current += 1
            if current > best:
                best, best_end = current, m.at
        else:
            current = 0
    return best, current, best_end


def player_insights(data, player, ranking_place=None):
    mine = [m for m in data.matches if player in (m.winner, m.loser)]
    wins = [m for m in mine if m.winner == player]
    finishes = [f for f in data.finishes if f["player"] == player]
    upsets = sorted((m for m in wins if m.factor > 0), key=lambda m: (-m.factor, m.at))
    best_streak, current_streak, _ = streaks(mine, player)
    comebacks = sum(1 for m in wins if m.comeback)
    titles = [f for f in finishes if f["placement"] == 1 and (f["entrants"] or 0) >= 8]
    top8 = [f for f in finishes if f["placement"] <= 8 and (f["entrants"] or 0) >= 16]
    over = sorted(
        (f for f in finishes if f["seed"] and f["placement"] < f["seed"]),
        key=lambda f: -(tier(f["seed"]) - tier(f["placement"])),
    )
    rivals = Counter(m.loser if m.winner == player else m.winner for m in mine)
    rival = rivals.most_common(1)[0] if rivals else None
    picks = data.picks.get(player, Counter())
    total_games = sum(picks.values())
    tournaments = {f["tournament_id"] for f in finishes}
    first_seen = min((f["starts_at"] for f in finishes if f["starts_at"]), default=None)
    latest = data.matches[-1].at if data.matches else None

    def match_view(m):
        return dict(
            set_id=m.id,
            opponent_id=str(m.loser if m.winner == player else m.winner),
            opponent=data.tags.get(m.loser if m.winner == player else m.winner),
            tournament=m.tournament,
            tournament_id=m.tournament_id,
            round=m.round,
            factor=m.factor,
            seed=m.winner_seed,
            opponent_seed=m.loser_seed,
            date=m.at.date().isoformat(),
        )

    records = dict(
        biggest_upset=match_view(upsets[0]) if upsets else None,
        best_streak=best_streak,
        current_streak=current_streak,
        comebacks=comebacks,
        titles=len(titles),
        top8=len(top8),
        tournaments=len(tournaments),
        best_overperformance=dict(
            tournament=over[0]["tournament"],
            tournament_id=over[0]["tournament_id"],
            seed=over[0]["seed"],
            placement=over[0]["placement"],
        )
        if over
        else None,
        main_rival=dict(id=str(rival[0]), tag=data.tags.get(rival[0]), sets=rival[1])
        if rival
        else None,
    )
    badges = []

    def badge(key, name, why):
        badges.append(dict(id=key, name=name, why=why))

    if ranking_place == 1:
        badge("lider", "Líder indiscutible", "Es el n.º 1 del ranking publicado.")
    if len(titles) >= 3:
        badge("trofeos", "Coleccionista de trofeos", f"Ganó {len(titles)} torneos.")
    elif titles:
        badge("campeon", "Campeón", f"Ganó {titles[0]['tournament']}.")
    if upsets and upsets[0].factor >= 3:
        u = upsets[0]
        badge(
            "david",
            "David contra Goliat",
            f"Siendo seed {u.winner_seed} le ganó a {data.tags.get(u.loser)} (seed {u.loser_seed}) "
            f"en {u.tournament}.",
        )
    if comebacks >= 5:
        badge(
            "remontadas",
            "Maestro de las remontadas",
            f"Ganó {comebacks} sets después de perder la primera partida.",
        )
    if best_streak >= 10:
        badge("racha", "Racha imparable", f"Ganó {best_streak} sets seguidos.")
    if len(top8) >= 5:
        badge(
            "top8",
            "Siempre en el top 8",
            f"Terminó {len(top8)} veces en el top 8 de torneos de 16 o más.",
        )
    if len(tournaments) >= 15:
        badge("incansable", "Incansable", f"Jugó {len(tournaments)} torneos.")
    if total_games >= 30:
        name, n = picks.most_common(1)[0]
        regular = [c for c, k in picks.items() if k >= 5]
        if n / total_games >= 0.9:
            badge(
                "especialista",
                "Especialista",
                f"Juega {name} en el {round(100 * n / total_games)} % de sus partidas.",
            )
        elif len(regular) >= 4:
            badge("camaleon", "Camaleón", f"Usa {len(regular)} personajes con frecuencia.")
    if first_seen and latest and latest - first_seen <= timedelta(days=60):
        badge("nuevo", "Nuevo en la escena", "Su primer torneo fue en los últimos dos meses.")
    return dict(records=records, badges=badges)


# ---------------------------------------------------------------- community


def player_of_month(data, days=30):
    if not data.matches:
        return None
    since = data.matches[-1].at - timedelta(days=days)
    recent = [m for m in data.matches if m.at >= since]
    score, wins, upsets = Counter(), Counter(), Counter()
    for m in recent:
        wins[m.winner] += 1
        score[m.winner] += 1 + 2 * min(m.factor, 3)
        if m.factor > 0:
            upsets[m.winner] += 1
    titles = Counter(
        f["player"]
        for f in data.finishes
        if f["placement"] == 1
        and f["starts_at"]
        and f["starts_at"] >= since
        and (f["entrants"] or 0) >= 8
    )
    for player, n in titles.items():
        score[player] += 5 * n
    if not score:
        return None
    player, points = score.most_common(1)[0]
    losses = sum(1 for m in recent if m.loser == player)
    return dict(
        id=str(player),
        tag=data.tags.get(player),
        wins=wins[player],
        losses=losses,
        upsets=upsets[player],
        titles=titles[player],
        since=since.date().isoformat(),
        until=data.matches[-1].at.date().isoformat(),
    )


def unique_upsets(matches):
    """Biggest upsets first, one per winner, loser and tournament (a reset repeats them)."""
    seen, result = set(), []
    ordered = sorted(
        (m for m in matches if m.factor > 0), key=lambda m: (-m.factor, -m.at.timestamp())
    )
    for m in ordered:
        key = (m.winner, m.loser, m.tournament_id)
        if key not in seen:
            seen.add(key)
            result.append(m)
    return result


def community_records(data, limit=5):
    players = {p for m in data.matches for p in (m.winner, m.loser)}
    streak_rows = []
    for p in players:
        best, _, end = streaks(data.matches, p)
        streak_rows.append((best, end, p))
    streak_rows.sort(key=lambda r: (-r[0], r[1] or 0))
    rivalries = Counter(frozenset((m.winner, m.loser)) for m in data.matches)
    head = Counter()
    for m in data.matches:
        head[(m.winner, m.loser)] += 1
    upsets = unique_upsets(data.matches)
    comebacks = Counter(m.winner for m in data.matches if m.comeback)
    tournaments = Counter()
    seen = set()
    for f in data.finishes:
        key = (f["player"], f["tournament_id"])
        if key not in seen:
            seen.add(key)
            tournaments[f["player"]] += 1
    titles = Counter(
        f["player"] for f in data.finishes if f["placement"] == 1 and (f["entrants"] or 0) >= 8
    )

    def who(p):
        return dict(id=str(p), tag=data.tags.get(p))

    return dict(
        player_of_month=player_of_month(data),
        streaks=[dict(**who(p), value=best) for best, _, p in streak_rows[:limit] if best],
        rivalries=[
            dict(
                a=who(a),
                b=who(b),
                sets=n,
                a_wins=head[(a, b)],
                b_wins=head[(b, a)],
            )
            for pair, n in rivalries.most_common(limit)
            for a, b in [sorted(pair, key=str)]
        ],
        upsets=[
            dict(
                winner=who(m.winner),
                loser=who(m.loser),
                factor=m.factor,
                winner_seed=m.winner_seed,
                loser_seed=m.loser_seed,
                tournament=m.tournament,
                tournament_id=m.tournament_id,
                date=m.at.date().isoformat(),
            )
            for m in upsets[:limit]
        ],
        comebacks=[dict(**who(p), value=n) for p, n in comebacks.most_common(limit)],
        most_active=[dict(**who(p), value=n) for p, n in tournaments.most_common(limit)],
        titles=[dict(**who(p), value=n) for p, n in titles.most_common(limit)],
    )


def tournament_summary(data, tournament_id, limit=8):
    finishes = [f for f in data.finishes if f["tournament_id"] == str(tournament_id)]
    if not finishes:
        return None
    biggest = max(
        {f["event_id"] for f in finishes},
        key=lambda e: sum(1 for f in finishes if f["event_id"] == e),
    )
    event = sorted(
        (f for f in finishes if f["event_id"] == biggest),
        key=lambda f: (f["placement"], f["seed"] or 9999),
    )
    matches = [m for m in data.matches if m.event_id == biggest]
    upsets = unique_upsets(matches)
    over = sorted(
        (f for f in event if f["seed"] and f["placement"] < f["seed"]),
        key=lambda f: -(tier(f["seed"]) - tier(f["placement"])),
    )
    return dict(
        event_id=biggest,
        entrants=event[0]["entrants"],
        top=[
            dict(
                id=str(f["player"]),
                tag=data.tags.get(f["player"]),
                placement=f["placement"],
                seed=f["seed"],
            )
            for f in event[:limit]
        ],
        upsets=[
            dict(
                winner=dict(id=str(m.winner), tag=data.tags.get(m.winner)),
                loser=dict(id=str(m.loser), tag=data.tags.get(m.loser)),
                factor=m.factor,
                winner_seed=m.winner_seed,
                loser_seed=m.loser_seed,
                round=m.round,
            )
            for m in upsets[:5]
        ],
        overperformers=[
            dict(
                id=str(f["player"]),
                tag=data.tags.get(f["player"]),
                seed=f["seed"],
                placement=f["placement"],
            )
            for f in over[:3]
        ],
    )


# ---------------------------------------------------------------- characters


def character_stats(data, top=3):
    """Characters of the scene: games, share, game win rate and who plays them most."""
    usage, wins = Counter(), Counter()
    by_player, player_wins = defaultdict(Counter), defaultdict(Counter)
    for g in data.games:
        for player, character in (g.a, g.b):
            usage[character] += 1
            by_player[character][player] += 1
            if g.winner == player:
                wins[character] += 1
                player_wins[character][player] += 1
    total = sum(usage.values())
    return [
        dict(
            character=character,
            games=n,
            share=round(100 * n / total, 1),
            win_rate=round(100 * wins[character] / n, 1),
            players=len(by_player[character]),
            top_players=[
                dict(
                    id=str(p),
                    tag=data.tags.get(p),
                    games=k,
                    win_rate=round(100 * player_wins[character][p] / k, 1),
                )
                for p, k in sorted(by_player[character].items(), key=lambda x: (-x[1], str(x[0])))[
                    :top
                ]
            ],
        )
        for character, n in sorted(usage.items(), key=lambda x: (-x[1], x[0]))
    ]


def matchups(data, player):
    """Games against each opposing character, most played first."""
    games, wins = Counter(), Counter()
    for g in data.games:
        for (p, _), (_, theirs) in ((g.a, g.b), (g.b, g.a)):
            if p == player:
                games[theirs] += 1
                wins[theirs] += g.winner == player
    return [
        dict(
            character=character,
            games=n,
            wins=wins[character],
            win_rate=round(100 * wins[character] / n, 1),
        )
        for character, n in sorted(games.items(), key=lambda x: (-x[1], x[0]))
    ]
