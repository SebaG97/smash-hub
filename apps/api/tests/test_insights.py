"""Insights: upset factor, badges, records and tournament summaries (no start.gg calls)."""

from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest

from app.insights import engine
from app.insights.engine import Data, Game, Match, tier, upset_factor

START = datetime(2026, 9, 1, 18, tzinfo=UTC)


def match(n, winner, loser, *, ws=None, ls=None, comeback=False, tournament="t1", days=0):
    return Match(
        id=f"s{n}",
        at=START + timedelta(days=days, minutes=n),
        tournament_id=tournament,
        tournament=f"Open {tournament}",
        event_id=f"e-{tournament}",
        round="Winners Round 1",
        winner=winner,
        loser=loser,
        winner_seed=ws,
        loser_seed=ls,
        comeback=comeback,
    )


def finish(player, placement, seed, *, entrants=16, tournament="t1", days=0):
    return dict(
        player=player,
        placement=placement,
        seed=seed,
        entrants=entrants,
        tournament_id=tournament,
        tournament=f"Open {tournament}",
        event_id=f"e-{tournament}",
        starts_at=START + timedelta(days=days),
    )


@pytest.mark.parametrize(
    "seed, expected", [(1, 0), (2, 1), (4, 3), (5, 4), (6, 4), (7, 5), (8, 5), (9, 6), (16, 7)]
)
def test_tiers_follow_double_elimination_placements(seed, expected):
    assert tier(seed) == expected


def test_upset_factor():
    assert upset_factor(9, 1) == 6
    assert upset_factor(4, 3) == 1
    assert upset_factor(5, 6) == 0  # same tier: not an upset
    assert upset_factor(1, 9) == 0  # the favourite won
    assert upset_factor(None, 1) == 0


def test_player_badges_and_records():
    data = Data(tags={"a": "Ana", "b": "Beto", "c": "Caro"})
    # Ana, seed 9, beats Beto (seed 1) after losing game one, then wins ten more in a row.
    data.matches.append(match(0, "a", "b", ws=9, ls=1, comeback=True))
    data.matches += [match(i, "a", "c", ws=9, ls=12, comeback=i <= 4) for i in range(1, 11)]
    data.matches.append(match(11, "b", "a", ws=1, ls=9))
    data.finishes = [finish("a", 1, 9, tournament=f"t{i}", days=i) for i in range(3)]
    data.picks = {"a": Counter({"Ryu": 40})}

    result = engine.player_insights(data, "a", ranking_place=1)
    ids = [b["id"] for b in result["badges"]]
    assert ids == ["lider", "trofeos", "david", "remontadas", "racha", "especialista", "nuevo"]
    records = result["records"]
    assert records["best_streak"] == 11
    assert records["current_streak"] == 0
    assert records["comebacks"] == 5
    assert records["titles"] == 3
    assert records["biggest_upset"]["opponent"] == "Beto"
    assert records["biggest_upset"]["factor"] == 6
    assert records["best_overperformance"] == {
        "tournament": "Open t0",
        "tournament_id": "t0",
        "seed": 9,
        "placement": 1,
    }
    assert records["main_rival"] == {"id": "c", "tag": "Caro", "sets": 10}


def test_small_events_do_not_count_as_titles():
    data = Data(tags={"a": "Ana"}, finishes=[finish("a", 1, 1, entrants=4)])
    result = engine.player_insights(data, "a")
    assert result["records"]["titles"] == 0
    assert "campeon" not in [b["id"] for b in result["badges"]]


def test_community_records_and_player_of_month():
    data = Data(tags={"a": "Ana", "b": "Beto"})
    data.matches = [
        match(0, "b", "a", ws=1, ls=2, days=-90),
        match(1, "a", "b", ws=5, ls=1, comeback=True),
        # A grand final reset repeats the same upset; it must be listed once.
        match(2, "a", "b", ws=5, ls=1),
    ]
    data.finishes = [finish("a", 1, 5), finish("b", 2, 1)]
    records = engine.community_records(data)
    assert records["player_of_month"]["tag"] == "Ana"
    assert records["player_of_month"]["wins"] == 2
    assert records["player_of_month"]["titles"] == 1
    assert len(records["upsets"]) == 1
    assert records["upsets"][0]["factor"] == 4
    rivalry = records["rivalries"][0]
    assert rivalry["sets"] == 3
    assert {rivalry["a"]["tag"]: rivalry["a_wins"], rivalry["b"]["tag"]: rivalry["b_wins"]} == {
        "Ana": 2,
        "Beto": 1,
    }
    assert records["streaks"][0] == {"id": "a", "tag": "Ana", "value": 2}
    assert records["comebacks"] == [{"id": "a", "tag": "Ana", "value": 1}]


def test_tournament_summary_uses_the_biggest_event():
    data = Data(tags={"a": "Ana", "b": "Beto", "c": "Caro"})
    data.finishes = [
        finish("b", 2, 1),
        finish("a", 1, 5),
        finish("c", 3, 2),
        dict(finish("a", 1, 1, entrants=2), event_id="doubles"),
    ]
    data.matches = [match(0, "a", "b", ws=5, ls=1)]
    summary = engine.tournament_summary(data, "t1")
    assert summary["event_id"] == "e-t1"
    assert [p["tag"] for p in summary["top"]] == ["Ana", "Beto", "Caro"]
    assert summary["upsets"][0]["factor"] == 4
    assert summary["overperformers"] == [{"id": "a", "tag": "Ana", "seed": 5, "placement": 1}]
    assert engine.tournament_summary(data, "missing") is None


def test_calendar_keeps_offline_paraguay_events(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from app.insights import router
    from app.main import create_app

    calls = []

    class FakeClient:
        def __init__(self, token):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def query(self, name, variables):
            calls.append((name, variables))
            return {
                "tournaments": {
                    "nodes": [
                        {
                            "name": "Center Stage 2026",
                            "slug": "tournament/center-stage-2026",
                            "startAt": 1794920400,
                            "city": "Asunción",
                            "venueName": None,
                            "numAttendees": 40,
                            "isOnline": False,
                        },
                        {"name": "Online weekly", "slug": "tournament/weekly", "isOnline": True},
                    ]
                }
            }

    monkeypatch.setattr(router, "StartGGClient", FakeClient)
    monkeypatch.setitem(router._calendar, "items", None)
    app = create_app(
        Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/x")
    )
    with TestClient(app) as client:
        first = client.get("/api/v1/insights/calendar").json()
        client.get("/api/v1/insights/calendar")
    assert [i["name"] for i in first["items"]] == ["Center Stage 2026"]
    assert first["items"][0]["url"] == "https://www.start.gg/tournament/center-stage-2026"
    assert first["items"][0]["starts_at"].startswith("2026-11-17")
    assert len(calls) == 1  # cached for an hour
    assert calls[0] == ("upcoming_tournaments", {"country": "PY", "videogame": "1386"})


def scene_games():
    """Ana (Ryu) and Beto (Ken / Ryu) over four games, Caro (Ken) once."""
    return Data(
        tags={"a": "Ana", "b": "Beto", "c": "Caro"},
        games=[
            Game(a=("a", "Ryu"), b=("b", "Ken"), winner="a"),
            Game(a=("a", "Ryu"), b=("b", "Ken"), winner="a"),
            Game(a=("b", "Ken"), b=("a", "Ryu"), winner="b"),
            Game(a=("a", "Ryu"), b=("b", "Ryu"), winner="b"),
            Game(a=("c", "Ken"), b=("a", "Ryu"), winner="c"),
        ],
    )


def test_character_stats():
    stats = engine.character_stats(scene_games())
    assert [
        (c["character"], c["games"], c["share"], c["win_rate"], c["players"]) for c in stats
    ] == [
        ("Ryu", 6, 60.0, 50.0, 2),
        ("Ken", 4, 40.0, 50.0, 2),
    ]
    assert stats[0]["top_players"][0] == {"id": "a", "tag": "Ana", "games": 5, "win_rate": 40.0}
    assert [p["tag"] for p in stats[1]["top_players"]] == ["Beto", "Caro"]


def test_matchups_count_each_opposing_character():
    assert engine.matchups(scene_games(), "a") == [
        {"character": "Ken", "games": 4, "wins": 2, "win_rate": 50.0},
        {"character": "Ryu", "games": 1, "wins": 0, "win_rate": 0.0},
    ]
    assert engine.matchups(scene_games(), "nobody") == []
