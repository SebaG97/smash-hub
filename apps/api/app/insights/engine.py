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
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

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
from app.competitions.roles import event_roles
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
    ranked: list = field(default_factory=list)  # players of the published ranking, in order
    month_winners: dict | None = None  # filled on demand by month_winners()


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
        select(
            Event.id,
            Tournament.id,
            Tournament.name,
            Tournament.starts_at,
            Event.num_entrants,
            Tournament.seeding_reliable,
            Event.name,
            Tournament.location,
        )
        .join(Tournament, Tournament.id == Event.tournament_id)
        .where(Tournament.published.is_(True), Event.team_size == 1)
    )
    events, unreliable, event_names, cities = {}, set(), {}, {}
    for e, t, name, starts, n, reliable, event_name, location in session.execute(singles):
        events[e] = (t, name, starts, n)
        event_names[e] = event_name
        cities[e] = (location or {}).get("city")
        if not reliable:
            unreliable.add(e)
    roles = event_roles(session)
    entrants = {
        # Seeds of wrongly seeded tournaments are dropped: no upsets, no "beat the seed".
        e_id: (event_id, None if event_id in unreliable else seed, place)
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

    data = Data(picks=dict(picks), ranked=ranked_players(session))
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
                    event=event_names[event_id],
                    city=cities[event_id],
                    # Mission 20: only main brackets give titles, podiums and top 8s.
                    main=roles.get(event_id, True),
                    starts_at=starts,
                )
            )
    return data


def ranked_players(session):
    """Hub players of the latest published ranking, best first (eligible rows only)."""
    from app.players.models import ExternalIdentity
    from app.seeding import service
    from app.seeding.models import SeedingProject

    project = session.scalar(
        select(SeedingProject)
        .where(
            SeedingProject.kind == "ranking",
            SeedingProject.published.is_(True),
            SeedingProject.current_run_id.is_not(None),
        )
        .order_by(SeedingProject.event_date.desc())
    )
    if project is None:
        return []
    rows = [r for r in service.view(session, project)["seeds"] if r.get("eligible", True)]
    keys = [f"player:{r['player_id']}" for r in rows]
    hub = dict(
        session.execute(
            select(ExternalIdentity.external_id, ExternalIdentity.player_id).where(
                ExternalIdentity.external_id.in_(keys)
            )
        ).all()
    )
    return [hub[k] for k in keys if k in hub]


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
    titles = [
        f
        for f in finishes
        if f.get("main", True) and f["placement"] == 1 and (f["entrants"] or 0) >= 8
    ]
    side_titles = [
        f
        for f in finishes
        if not f.get("main", True) and f["placement"] == 1 and (f["entrants"] or 0) >= 8
    ]
    top8 = [
        f
        for f in finishes
        if f.get("main", True) and f["placement"] <= 8 and (f["entrants"] or 0) >= 16
    ]
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
    if side_titles:
        f = side_titles[0]
        badge(
            "amateur",
            "Campeón amateur",
            f"Ganó {f['event']} en {f['tournament']}."
            if len(side_titles) == 1
            else f"Ganó {len(side_titles)} eventos secundarios (amateur, ladder…).",
        )
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
    won_months = month_winners(data).get(str(player), [])
    if won_months:
        month, region = won_months[-1]
        badge(
            "mes",
            "Jugador del mes",
            f"Fue jugador del mes de {region} en {month_name(month)}."
            if len(won_months) == 1
            else f"Fue jugador del mes {len(won_months)} veces; la última, de {region} en "
            f"{month_name(month)}.",
        )
    if first_seen and latest and latest - first_seen <= timedelta(days=60):
        badge("nuevo", "Nuevo en la escena", "Su primer torneo fue en los últimos dos meses.")
    return dict(records=records, badges=badges)


# ---------------------------------------------------------------- community


# Player of the month (Mission 21): what a player did in the month's tournaments against
# what was expected of them, per region, so a scene that rarely travels gets its own.
REGIONS = {"central": "Gran Asunción", "cde": "Ciudad del Este"}
EAST = {
    "Ciudad del Este",
    "Hernandarias",
    "Minga Guazú",
    "Presidente Franco",
    "Santa Rita",
    "Encarnación",
    "Salto del Guairá",
}
PLACE_POINTS = {1: 15, 2: 10, 3: 7, 4: 5, 5: 3, 6: 3, 7: 2, 8: 2, 9: 1, 10: 1, 11: 1, 12: 1}
BEST_OF = 3  # tournaments that count per player and month
ASUNCION = ZoneInfo("America/Asuncion")
MONTHS = (
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre"
).split()


def month_name(month):
    year, number = month.split("-")
    return f"{MONTHS[int(number) - 1]} de {year}"


def region_of(city):
    """Tournaments in Alto Paraná and nearby count for Ciudad del Este, the rest for Asunción."""
    return "cde" if city in EAST else "central"


def month_of(at):
    return at.astimezone(ASUNCION).strftime("%Y-%m")


def month_scores(data, month, region):
    """Players of a region's main events in a month, best first, with how they scored.

    Per tournament: placement points (15, 10, 7, 5, 3, 3, 2, 2, then 1 down to 12th) times
    the bracket size (x0.5 for 8 players, x1 for 16, x2 for 32 or more); +2 per bracket
    tier above their seed (at most +10); +1.5 per tier of each upset won (+2 more against
    a top 10 of the ranking); -1 per tier of each upset lost. Seed and upset points are
    weighted by how many of the ranking's top 20 played (x0.6 to x1.4). The best three
    tournaments of the month count.
    """
    finishes = [
        f
        for f in data.finishes
        if f.get("main", True)
        and f["starts_at"]
        and month_of(f["starts_at"]) == month
        and region_of(f.get("city")) == region
    ]
    if not finishes:
        return []
    top20, top10 = set(data.ranked[:20]), set(data.ranked[:10])
    events = {f["event_id"] for f in finishes}
    strength = Counter(f["event_id"] for f in finishes if f["player"] in top20)
    won, lost = defaultdict(list), defaultdict(list)
    for m in data.matches:
        if m.event_id in events and m.factor > 0:
            won[(m.winner, m.event_id)].append(m)
            lost[(m.loser, m.event_id)].append(m)
    results = defaultdict(list)
    for f in finishes:
        e, p = f["event_id"], f["player"]
        size = min(max((f["entrants"] or 0) / 16, 0.5), 2)
        level = min(max(0.6 + 0.08 * strength[e], 0.6), 1.4)
        place = PLACE_POINTS.get(f["placement"], 0) * size
        seed = min(2 * max(tier(f["seed"]) - tier(f["placement"]), 0), 10) if f["seed"] else 0
        upsets = won[(p, e)]
        bonus = sum(1.5 * min(m.factor, 3) + (2 if m.loser in top10 else 0) for m in upsets)
        slips = sum(min(m.factor, 3) for m in lost[(p, e)])
        results[p].append(
            dict(
                tournament=f["tournament"],
                tournament_id=f["tournament_id"],
                placement=f["placement"],
                entrants=f["entrants"],
                seed=f["seed"],
                upsets=len(upsets),
                top10_wins=sum(1 for m in upsets if m.loser in top10),
                points=round(place + (seed + bonus - slips) * level, 1),
            )
        )
    rows = []
    for p, mine in results.items():
        best = sorted(mine, key=lambda r: -r["points"])[:BEST_OF]
        rows.append(
            dict(
                id=str(p),
                tag=data.tags.get(p),
                points=round(sum(r["points"] for r in best), 1),
                results=best,
            )
        )
    return sorted(rows, key=lambda r: (-r["points"], r["tag"] or ""))


def months_played(data):
    return sorted(
        {month_of(f["starts_at"]) for f in data.finishes if f.get("main", True) and f["starts_at"]}
    )


def player_of_month(data, month=None, now=None):
    """The month's best player per region; the latest month with results by default."""
    months = months_played(data)
    if not months:
        return None
    month = month or months[-1]
    current = month_of(now or datetime.now(UTC))
    regions = []
    for key, name in REGIONS.items():
        rows = month_scores(data, month, key)
        regions.append(
            dict(
                region=key,
                name=name,
                winner=rows[0] if rows and rows[0]["points"] > 0 else None,
                runners=[dict(id=r["id"], tag=r["tag"], points=r["points"]) for r in rows[1:3]],
            )
        )
    return dict(
        month=month,
        label=month_name(month),
        in_progress=month == current,
        months=months,
        regions=regions,
    )


def month_winners(data, now=None):
    """{player id: [(month, region name)]} over finished months, for the badge."""
    if data.month_winners is None:
        current = month_of(now or datetime.now(UTC))
        winners = defaultdict(list)
        for month in months_played(data):
            if month == current:
                continue
            for key, name in REGIONS.items():
                rows = month_scores(data, month, key)
                if rows and rows[0]["points"] > 0:
                    winners[rows[0]["id"]].append((month, name))
        data.month_winners = dict(winners)
    return data.month_winners


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
        f["player"]
        for f in data.finishes
        if f.get("main", True) and f["placement"] == 1 and (f["entrants"] or 0) >= 8
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


def tournament_summary(data, tournament_id, limit=8, event_id=None):
    """Podium, upsets and overperformers of one singles event of the tournament: the one
    asked for, else the main one (the biggest main event, or the biggest at all)."""
    finishes = [f for f in data.finishes if f["tournament_id"] == str(tournament_id)]
    if not finishes:
        return None
    sizes = Counter(f["event_id"] for f in finishes)
    info = {f["event_id"]: f for f in finishes}
    events = sorted(
        sizes,
        key=lambda e: (not info[e].get("main", True), -sizes[e], info[e].get("event") or ""),
    )
    if event_id is not None and str(event_id) not in sizes:
        return None
    chosen = str(event_id) if event_id is not None else events[0]
    event = sorted(
        (f for f in finishes if f["event_id"] == chosen),
        key=lambda f: (f["placement"], f["seed"] or 9999),
    )
    matches = [m for m in data.matches if m.event_id == chosen]
    upsets = unique_upsets(matches)
    over = sorted(
        (f for f in event if f["seed"] and f["placement"] < f["seed"]),
        key=lambda f: -(tier(f["seed"]) - tier(f["placement"])),
    )
    return dict(
        event_id=chosen,
        event=info[chosen].get("event"),
        main=info[chosen].get("main", True),
        # Every singles bracket of the tournament, main first, to switch between them.
        events=[
            dict(
                id=e,
                name=info[e].get("event"),
                main=info[e].get("main", True),
                entrants=info[e]["entrants"] or sizes[e],
            )
            for e in events
        ],
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
