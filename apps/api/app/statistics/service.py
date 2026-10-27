from sqlalchemy import func, select

from app.competitions.router import visible_players
from app.integrations.startgg.client import ImportFailure, parse_slug
from app.players.mains import player_mains
from app.players.models import Player
from app.statistics import repository as repo
from app.statistics.contracts import Filters


class PlayerNotFound(Exception):
    pass


class SelfComparison(Exception):
    pass


def percentage(wins, count):
    return round(wins / count * 100, 2) if count else None


def player(session, id):
    row = session.scalar(visible_players().where(Player.id == id))
    if row is None:
        raise PlayerNotFound
    return {"id": row.id, "tag": row.tag}


def metadata(filters):
    return Filters.model_validate(filters.model_dump(exclude={"page", "page_size"}))


def listing(items, total, filters):
    return {
        "items": items,
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size,
        "filters": metadata(filters),
    }


def match_views(session, rows):
    ids = {id for row in rows for id in row["opponent_ids"]}
    tags = dict(session.execute(select(Player.id, Player.tag).where(Player.id.in_(ids))).all())
    result = []
    for row in rows:
        source_url = None
        if row["source"] == "start.gg":
            try:
                source_url = "https://www.start.gg/tournament/" + parse_slug(row["tournament_slug"])
            except ImportFailure:
                pass
        result.append(
            {
                **{
                    k: v
                    for k, v in row.items()
                    if k not in {"opponent_ids", "opponent_entrant_id", "won", "tournament_slug"}
                },
                "result": "W" if row["won"] else "L",
                "opponents": [{"id": id, "tag": tags[id]} for id in sorted(row["opponent_ids"])],
                "source_url": source_url,
            }
        )
    return result


def statistics(session, id, filters):
    identity = player(session, id)
    matches = repo.perspective(repo.eligible_sets(session, filters), id)
    result = dict(repo.summary(session, matches))
    latest = (
        session.execute(
            repo.ordered_matches(matches).where(matches.c.completed_at.is_not(None)).limit(1)
        )
        .mappings()
        .first()
    )
    registrations = repo.registrations(filters, id).subquery()
    tournaments_registered = session.scalar(
        select(func.count(func.distinct(registrations.c.tournament_id)))
    )
    best = session.scalar(
        select(func.min(registrations.c.placement)).where(registrations.c.placement > 0)
    )
    unique = session.scalar(
        select(func.count()).select_from(repo.opponents(matches).order_by(None).subquery())
    )
    return {
        **result,
        "player": identity,
        "filters": metadata(filters),
        "win_rate": percentage(result["wins"], result["sets_played"]),
        "tournaments_registered": tournaments_registered,
        "latest_tournament": {"id": latest["tournament_id"], "name": latest["tournament_name"]}
        if latest
        else None,
        "best_final_placement": best,
        "unique_opponents": unique,
    }


def matches(session, id, filters):
    player(session, id)
    data = repo.perspective(repo.eligible_sets(session, filters), id)
    rows, total = repo.page(session, repo.ordered_matches(data), filters.page, filters.page_size)
    return listing(match_views(session, rows), total, filters)


def opponents(session, id, filters):
    player(session, id)
    data = repo.perspective(repo.eligible_sets(session, filters), id)
    rows, total = repo.page(session, repo.opponents(data), filters.page, filters.page_size)
    mains = player_mains(session, [row["id"] for row in rows], limit=1)
    items = [
        {
            **{k: v for k, v in row.items() if k not in {"id", "tag"}},
            "opponent": {"id": row["id"], "tag": row["tag"], "mains": mains.get(row["id"], [])},
            "win_rate": percentage(row["wins"], row["sets_played"]),
        }
        for row in rows
    ]
    return listing(items, total, filters)


def placements(session, id, filters):
    player(session, id)
    rows, total = repo.page(session, repo.placements(filters, id), filters.page, filters.page_size)
    return listing(rows, total, filters)


def head_to_head(session, id, opponent_id, filters):
    if id == opponent_id:
        raise SelfComparison
    a, b = player(session, id), player(session, opponent_id)
    data = repo.perspective(repo.eligible_sets(session, filters), id, opponent_id)
    summary = repo.summary(session, data)
    rows, total = repo.page(
        session, repo.ordered_matches(data, ascending=True), filters.page, filters.page_size
    )
    return {
        "player_a": a,
        "player_b": b,
        "filters": metadata(filters),
        "encounters": summary["sets_played"],
        "wins_a": summary["wins"],
        "wins_b": summary["losses"],
        "win_rate_a": percentage(summary["wins"], summary["sets_played"]),
        "win_rate_b": percentage(summary["losses"], summary["sets_played"]),
        "first_encounter_at": summary["first_set_at"],
        "last_encounter_at": summary["last_set_at"],
        "history": listing(match_views(session, rows), total, filters),
    }
