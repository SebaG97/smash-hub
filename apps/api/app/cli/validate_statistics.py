"""Read-only local audit. No provider requests, migrations, or data writes."""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.competitions.models import Event, Set, Tournament, TournamentParticipant
from app.core.config import get_settings
from app.database import models  # noqa: F401
from app.database.session import build_engine
from app.statistics import repository as repo
from app.statistics import service
from app.statistics.contracts import Filters, HeadToHeadView, ListingFilters, StatisticsView


def audit(session, slugs):
    tournaments = session.scalars(select(Tournament).where(Tournament.slug.in_(slugs))).all()
    if {t.slug for t in tournaments} != set(slugs) or not all(t.published for t in tournaments):
        raise ValueError("All requested local tournaments must exist and be published")
    ids = [t.id for t in tournaments]
    games = session.scalars(
        select(Event.game_id).where(Event.tournament_id.in_(ids)).distinct()
    ).all()
    result = {
        "audited_at": datetime.now(UTC).isoformat(),
        "read_only": True,
        "tournaments": [],
        "games": [],
    }
    for t in sorted(tournaments, key=lambda t: t.slug):
        resolution = dict(
            session.execute(
                select(Set.resolution, func.count())
                .join(Event)
                .where(Event.tournament_id == t.id)
                .group_by(Set.resolution)
            ).all()
        )
        valid = sum(
            session.scalar(
                select(func.count()).select_from(
                    repo.eligible_sets(session, Filters(game_id=game, tournament_id=t.id))
                )
            )
            for game in games
        )
        result["tournaments"].append(
            {"slug": t.slug, "id": str(t.id), "resolution": resolution, "eligible_singles": valid}
        )
    shared = Counter(
        session.scalars(
            select(TournamentParticipant.player_id).where(
                TournamentParticipant.tournament_id.in_(ids)
            )
        ).all()
    )
    result["players"] = {
        "unique": len(shared),
        "multiple_tournaments": sum(n > 1 for n in shared.values()),
        "all_tournaments": sum(n == len(tournaments) for n in shared.values()),
    }
    for game in games:
        filters = Filters(game_id=game)
        universe = repo.eligible_sets(session, filters)
        rows = (
            session.execute(select(universe).where(universe.c.tournament_id.in_(ids)))
            .mappings()
            .all()
        )
        wins, losses = Counter(), Counter()
        for row in rows:
            assert len(row["players_a"]) == len(row["players_b"]) == 1
            a, b = row["players_a"][0], row["players_b"][0]
            wins[a if row["a_won"] else b] += 1
            losses[b if row["a_won"] else a] += 1
        assert len({r["id"] for r in rows}) == len(rows)
        assert sum(wins.values()) == sum(losses.values()) == len(rows)
        # Check every participant's actual statistics against the individual sets.
        # If other published tournaments exist, restrict this reconciliation to
        # each requested tournament rather than comparing unrelated universes.
        for t in tournaments:
            per_t = [r for r in rows if r["tournament_id"] == t.id]
            for player_id in shared:
                stats = service.statistics(
                    session, player_id, Filters(game_id=game, tournament_id=t.id)
                )
                expected_w = sum(
                    (player_id in r["players_a"] and r["a_won"])
                    or (player_id in r["players_b"] and not r["a_won"])
                    for r in per_t
                )
                expected_l = sum(
                    (player_id in r["players_a"] and not r["a_won"])
                    or (player_id in r["players_b"] and r["a_won"])
                    for r in per_t
                )
                assert stats["wins"] == expected_w and stats["losses"] == expected_l
        game_result = {
            "game_id": str(game),
            "eligible_sets": len(rows),
            "wins": sum(wins.values()),
            "losses": sum(losses.values()),
            "distinct_sets": len({r["id"] for r in rows}),
            "every_player_reconciled": True,
        }
        if rows:
            chosen = max(set(wins) | set(losses), key=lambda p: (wins[p] + losses[p], str(p)))
            stats = StatisticsView.model_validate(service.statistics(session, chosen, filters))
            listing = ListingFilters(game_id=game)
            rivals = service.opponents(session, chosen, listing)
            opponent = rivals["items"][0]["opponent"]["id"]
            h2h = HeadToHeadView.model_validate(
                service.head_to_head(session, chosen, opponent, listing)
            )
            reverse = service.head_to_head(session, opponent, chosen, listing)
            assert h2h.encounters == reverse["encounters"] and h2h.wins_a == reverse["wins_b"]
            game_result["player_example"] = stats.model_dump(mode="json")
            game_result["head_to_head_example"] = h2h.model_dump(mode="json")
            player_sets = repo.perspective(universe, chosen)
            plans = {}
            for name, stmt in {
                "eligible_universe": select(universe),
                "recent_matches": repo.ordered_matches(player_sets).limit(20),
                "opponents": repo.opponents(player_sets).limit(20),
            }.items():
                compiled = stmt.compile(
                    dialect=session.bind.dialect, compile_kwargs={"literal_binds": True}
                )
                plan = session.scalar(
                    text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + str(compiled))
                )[0]
                plans[name] = {
                    "planning_ms": plan["Planning Time"],
                    "execution_ms": plan["Execution Time"],
                    "plan": plan["Plan"],
                }
            game_result["query_plans"] = plans
        result["games"].append(game_result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slugs", nargs="+", required=True)
    args = parser.parse_args()
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.environment != "development"
        or url.host not in {"postgres", "localhost", "127.0.0.1"}
        or url.database != "smashhub"
    ):
        raise SystemExit("Refusing anything except the dedicated local development database")
    engine = build_engine(settings)
    try:
        with Session(engine) as session:
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            session.execute(text("SET TRANSACTION READ ONLY"))
            result = audit(session, args.slugs)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
