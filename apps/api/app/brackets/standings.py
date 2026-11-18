"""Final standings of one event: every entrant with how their day went.

``standings`` is pure (tested without a database); ``event_standings`` reads the rows.
"""

from collections import Counter, defaultdict

from sqlalchemy import select

from app.brackets.service import _players
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
from app.games.models import Character
from app.insights.engine import tier, upset_factor


def _order(s):
    # Undated sets go last; start.gg round numbers break ties inside a day.
    return (s["completed_at"] is None, s["completed_at"], abs(s["round_number"] or 0))


def standings(entrants, sets, characters, *, reliable=True):
    """``entrants``: {id, name, seed, placement, prefix, members}; ``sets``: played sets as
    {winner, loser, winner_score, loser_score, round_label, round_number, completed_at};
    ``characters``: {entrant id: [{name, icon, games}]}. Upsets only with reliable seeds."""
    by_id = {e["id"]: e for e in entrants}
    record = defaultdict(lambda: {"wins": 0, "losses": 0, "games_won": 0, "games_lost": 0})
    beaten = defaultdict(list)
    lost_to = defaultdict(list)
    upsets = Counter()
    for s in sorted(sets, key=_order):
        w, lo = s["winner"], s["loser"]
        record[w]["wins"] += 1
        record[lo]["losses"] += 1
        for who, mine, theirs in (
            (w, "winner_score", "loser_score"),
            (lo, "loser_score", "winner_score"),
        ):
            if (s[mine] or 0) > 0:
                record[who]["games_won"] += s[mine]
            if (s[theirs] or 0) > 0:
                record[who]["games_lost"] += s[theirs]
        beaten[w].append(s)
        lost_to[lo].append(s)
        if reliable and upset_factor(by_id.get(w, {}).get("seed"), by_id.get(lo, {}).get("seed")):
            upsets[w] += 1

    def ref(entrant_id, s, mine, theirs):
        other = by_id.get(entrant_id, {})
        members = other.get("members") or []
        return {
            "name": other.get("name") or "?",
            "player_id": members[0]["player_id"] if len(members) == 1 else None,
            "seed": other.get("seed"),
            "score": f"{s[mine]}–{s[theirs]}"
            if s[mine] is not None and s[theirs] is not None and min(s[mine], s[theirs]) >= 0
            else None,
            "round": s["round_label"],
        }

    rows = []
    for e in entrants:
        seed, place = e.get("seed"), e.get("placement")
        losses = lost_to[e["id"]]
        wins = beaten[e["id"]]
        best = min(
            wins,
            key=lambda s: (by_id.get(s["loser"], {}).get("seed") or 10**6, _order(s)),
            default=None,
        )
        rows.append(
            {
                **e,
                **record[e["id"]],
                # Positive: finished more placement tiers above their seed than expected.
                "performance": tier(seed) - tier(place) if seed and place else None,
                "upsets": upsets[e["id"]],
                "eliminated_by": ref(
                    losses[-1]["winner"], losses[-1], "winner_score", "loser_score"
                )
                if losses and place and place != 1
                else None,
                "best_win": ref(best["loser"], best, "winner_score", "loser_score")
                if best
                else None,
                "characters": characters.get(e["id"], [])[:3],
            }
        )
    rows.sort(
        key=lambda r: (
            r["placement"] is None,
            r["placement"] or 0,
            r["seed"] is None,
            r["seed"] or 0,
            r["name"].casefold(),
        )
    )
    return rows


def event_standings(session, event_id):
    """None when the event does not exist or its tournament is not published."""
    event = session.get(Event, event_id)
    if event is None:
        return None
    tournament = session.get(Tournament, event.tournament_id)
    if tournament is None or not tournament.published:
        return None
    rows = session.scalars(select(EventEntrant).where(EventEntrant.event_id == event.id)).all()
    ids = [r.id for r in rows]
    people = _players(session, event, ids)
    members = defaultdict(list)
    for entrant_id, player_id, tag in session.execute(
        select(
            EntrantMember.entrant_id,
            TournamentParticipant.player_id,
            TournamentParticipant.tag_snapshot,
        )
        .join(TournamentParticipant, TournamentParticipant.id == EntrantMember.participant_id)
        .where(EntrantMember.entrant_id.in_(ids))
        .order_by(EntrantMember.position)
    ):
        members[entrant_id].append({"player_id": player_id, "tag": tag})
    entrants = [
        {
            "id": r.id,
            "name": (people.get(r.id) or {}).get("tag") or r.name,
            "seed": r.seed,
            "placement": r.placement if r.placement and r.placement > 0 else None,
            "prefix": (people.get(r.id) or {}).get("prefix"),
            "members": members.get(r.id, []),
        }
        for r in rows
    ]
    played = session.scalars(
        select(Set).where(Set.event_id == event.id, Set.resolution == "played")
    ).all()
    sides = defaultdict(dict)
    for side in session.scalars(select(SetSide).where(SetSide.set_id.in_([s.id for s in played]))):
        sides[side.set_id][side.side] = side
    sets = []
    for s in played:
        a, b = sides[s.id].get(1), sides[s.id].get(2)
        if not a or not b or not a.entrant_id or not b.entrant_id or a.is_winner == b.is_winner:
            continue
        w, lo = (a, b) if a.is_winner else (b, a)
        sets.append(
            {
                "winner": w.entrant_id,
                "loser": lo.entrant_id,
                "winner_score": w.score,
                "loser_score": lo.score,
                "round_label": s.round_label,
                "round_number": s.round_number,
                "completed_at": s.completed_at,
            }
        )
    picks = defaultdict(Counter)
    icons = {}
    for entrant_id, name, icon in session.execute(
        select(SetSelection.entrant_id, Character.name, Character.image_url)
        .join(Character, Character.id == SetSelection.character_id)
        .where(SetSelection.event_id == event.id)
    ):
        picks[entrant_id][name] += 1
        icons[name] = icon
    characters = {
        entrant_id: [
            {"name": name, "icon": icons[name], "games": n}
            for name, n in sorted(counter.items(), key=lambda x: (-x[1], x[0]))
        ]
        for entrant_id, counter in picks.items()
    }
    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "entrants": event.num_entrants or len(rows),
            "team_size": event.team_size,
        },
        "reliable": tournament.seeding_reliable,
        "sets": len(sets),
        "entrants": standings(entrants, sets, characters, reliable=tournament.seeding_reliable),
    }
