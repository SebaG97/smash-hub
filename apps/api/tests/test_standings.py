"""Event standings: placements with how each entrant's day went."""

import copy
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_brackets import bracket_set
from test_startgg import prepare, run
from test_startgg import snapshot as snapshot

from app.brackets.standings import standings
from app.competitions.models import Set
from app.core.config import Settings
from app.main import create_app


def entrant(id, seed, placement):
    return dict(
        id=id,
        name=id.title(),
        seed=seed,
        placement=placement,
        prefix=None,
        members=[dict(player_id=f"p-{id}", tag=id.title())],
    )


def played(winner, loser, ws, ls, hour, label):
    return dict(
        winner=winner,
        loser=loser,
        winner_score=ws,
        loser_score=ls,
        round_label=label,
        round_number=1,
        completed_at=datetime(2026, 11, 14, hour, tzinfo=UTC),
    )


ENTRANTS = [
    entrant("ace", 1, 2),
    entrant("bee", 2, 4),
    entrant("cid", 4, 1),
    entrant("dot", 3, None),
]
SETS = [
    played("cid", "ace", 2, 1, 15, "Winners Semis"),
    played("bee", "dot", 2, 0, 15, "Winners Semis"),
    played("ace", "bee", 2, 0, 16, "Losers Final"),
    played("cid", "ace", 3, 2, 17, "Grand Final"),
]


def test_standings_order_records_and_who_knocked_them_out():
    rows = standings(ENTRANTS, SETS, {"cid": [dict(name="Joker", icon=None, games=5)]})
    assert [r["id"] for r in rows] == ["cid", "ace", "bee", "dot"]
    cid, ace, bee, dot = rows
    assert (cid["wins"], cid["losses"], cid["games_won"], cid["games_lost"]) == (2, 0, 5, 3)
    assert cid["eliminated_by"] is None and cid["characters"][0]["name"] == "Joker"
    # Seed 4 winning the event: three placement tiers above expectations, two upset wins.
    assert cid["performance"] == 3 and cid["upsets"] == 2
    assert ace["eliminated_by"] == dict(
        name="Cid", player_id="p-cid", seed=4, score="3–2", round="Grand Final"
    )
    assert ace["best_win"]["name"] == "Bee"
    assert bee["performance"] == -2  # seed 2, finished 4th
    # No final placement: no "knocked out by", and it goes last.
    assert dot["eliminated_by"] is None and dot["performance"] is None


def test_unreliable_seeds_mark_no_upsets():
    rows = standings(ENTRANTS, SETS, {}, reliable=False)
    assert all(r["upsets"] == 0 for r in rows)


def test_standings_endpoint(db, snapshot):
    prepare(db)
    source = copy.deepcopy(snapshot)
    source["events"][0]["sets"] = [bracket_set(2001, 1, 71)]
    run(db, source)
    with Session(db) as s:
        event_id = s.scalar(select(Set.event_id).where(Set.round_label == "Winners Round 1"))
    with TestClient(
        create_app(
            Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/x"),
            engine=db,
        )
    ) as c:
        body = c.get(f"/api/v1/events/{event_id}/standings").json()
        assert body["sets"] == 1
        winner = next(r for r in body["entrants"] if r["wins"] == 1)
        assert winner["losses"] == 0 and winner["members"]
        assert (
            c.get("/api/v1/events/00000000-0000-0000-0000-000000000000/standings").status_code
            == 404
        )
