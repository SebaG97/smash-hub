from sqlalchemy import select

from app.competitions.router import visible_players
from app.integrations.startgg.client import ImportFailure, parse_slug
from app.players.mains import player_mains
from app.players.models import Player
from app.statistics import repository as repo
from app.statistics.breakdown import breakdown as build_breakdown
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
    from app.competitions.models import EventEntrant, SetSelection, Tournament
    from app.games.models import Character
    from app.insights.engine import upset_factor

    ids = {id for row in rows for id in row["opponent_ids"]}
    tags = dict(session.execute(select(Player.id, Player.tag).where(Player.id.in_(ids))).all())
    entrants = {row["entrant_id"] for row in rows} | {row["opponent_entrant_id"] for row in rows}
    seeds = dict(
        session.execute(
            select(EventEntrant.id, EventEntrant.seed).where(EventEntrant.id.in_(entrants))
        ).all()
    )
    reliable = dict(
        session.execute(
            select(Tournament.id, Tournament.seeding_reliable).where(
                Tournament.id.in_({row["tournament_id"] for row in rows})
            )
        ).all()
    )
    picks = {}
    for set_id, entrant_id, name, icon in session.execute(
        select(SetSelection.set_id, SetSelection.entrant_id, Character.name, Character.image_url)
        .join(Character, Character.id == SetSelection.character_id)
        .where(SetSelection.set_id.in_([row["id"] for row in rows]))
        .order_by(SetSelection.game_number)
    ):
        chosen = picks.setdefault((set_id, entrant_id), {})
        chosen.setdefault(name, {"name": name, "icon": icon})
    result = []
    for row in rows:
        source_url = None
        if row["source"] == "start.gg":
            try:
                source_url = "https://www.start.gg/tournament/" + parse_slug(row["tournament_slug"])
            except ImportFailure:
                pass
        seed, opponent_seed = seeds.get(row["entrant_id"]), seeds.get(row["opponent_entrant_id"])
        winner, loser = (seed, opponent_seed) if row["won"] else (opponent_seed, seed)
        result.append(
            {
                **{
                    k: v
                    for k, v in row.items()
                    if k
                    not in {
                        "opponent_ids",
                        "opponent_entrant_id",
                        "entrant_id",
                        "won",
                        "tournament_slug",
                    }
                },
                "result": "W" if row["won"] else "L",
                "opponents": [{"id": id, "tag": tags[id]} for id in sorted(row["opponent_ids"])],
                "source_url": source_url,
                "seed": seed,
                "opponent_seed": opponent_seed,
                "upset": bool(
                    reliable.get(row["tournament_id"], True) and upset_factor(winner, loser)
                ),
                "characters": list(picks.get((row["id"], row["entrant_id"]), {}).values()),
                "opponent_characters": list(
                    picks.get((row["id"], row["opponent_entrant_id"]), {}).values()
                ),
            }
        )
    return result


def ranking_places(session):
    """{hub player id: place} in the latest published ranking, and that ranking's name."""
    from app.insights.engine import ranked_players
    from app.seeding.models import SeedingProject

    name = session.scalar(
        select(SeedingProject.name)
        .where(
            SeedingProject.kind == "ranking",
            SeedingProject.published.is_(True),
            SeedingProject.current_run_id.is_not(None),
        )
        .order_by(SeedingProject.event_date.desc())
    )
    if name is None:
        return {}, None
    return {pid: i + 1 for i, pid in enumerate(ranked_players(session))}, name


def breakdown(session, id, filters):
    identity = player(session, id)
    data = repo.perspective(repo.eligible_sets(session, filters), id)
    rows = list(session.execute(select(data)).mappings())
    places, ranking = ranking_places(session) if filters.mode == "singles" else ({}, None)
    ids = {p for r in rows for p in r["opponent_ids"]}
    tags = dict(session.execute(select(Player.id, Player.tag).where(Player.id.in_(ids))).all())
    placements = session.execute(select(repo.placements(filters, id).subquery())).mappings()
    return {
        **build_breakdown(
            rows,
            list(placements),
            places=places,
            tags=tags,
            characters=repo.characters(session, data, id),
        ),
        "player": identity,
        "filters": metadata(filters),
        "ranking": ranking if places else None,
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
