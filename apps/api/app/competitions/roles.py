"""Main and secondary events of a tournament (Mission 20).

A tournament can run several singles brackets: the main one plus an amateur, a ladder or
a "pre" event. Only main events feed the rankings, titles, podiums and the player of the
month. Organizers decide per event; until they do, a rule guesses: an event is secondary
when its name (or the tournament's) says so, or when it is not the biggest singles
bracket of its game in the tournament.
"""

import re
from collections import defaultdict

from sqlalchemy import func, select

SECONDARY = re.compile(
    r"amateur|ladder|novat|principiante|beginner|redemption|\bpre\b", re.IGNORECASE
)


def guess(rows):
    """rows: dicts with id, tournament_id, tournament, name, game_id, entrants, manual.

    Returns {event id: main?}: the organizer's choice when there is one, else the rule.
    """
    groups = defaultdict(list)
    for r in rows:
        groups[(r["tournament_id"], r["game_id"])].append(r)
    result = {}
    for group in groups.values():
        candidates = [
            r
            for r in group
            if not SECONDARY.search(r["name"] or "") and not SECONDARY.search(r["tournament"] or "")
        ]
        biggest = max(candidates, key=lambda r: r["entrants"] or 0, default=None)
        for r in group:
            auto = biggest is not None and r["id"] == biggest["id"]
            result[r["id"]] = auto if r["manual"] is None else r["manual"]
    return result


def event_roles(session, tournament_ids=None):
    """{event id: main?} for the singles events of published tournaments."""
    from app.competitions.models import Event, EventEntrant, Tournament

    counted = (
        select(EventEntrant.event_id, func.count().label("n"))
        .group_by(EventEntrant.event_id)
        .subquery()
    )
    query = (
        select(
            Event.id,
            Event.tournament_id,
            Tournament.name.label("tournament"),
            Event.name,
            Event.game_id,
            func.coalesce(Event.num_entrants, counted.c.n).label("entrants"),
            Event.main.label("manual"),
        )
        .join(Tournament, Tournament.id == Event.tournament_id)
        .outerjoin(counted, counted.c.event_id == Event.id)
        .where(Tournament.published.is_(True), Event.team_size == 1)
    )
    if tournament_ids is not None:
        query = query.where(Event.tournament_id.in_(list(tournament_ids)))
    return guess(session.execute(query).mappings().all())
