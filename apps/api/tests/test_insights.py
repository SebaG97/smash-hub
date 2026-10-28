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


def test_preview_picks_the_offline_ultimate_singles_event():
    from app.insights.preview import singles_event

    events = [
        {"id": 1, "numEntrants": 90, "videogame": {"id": 1386}, "isOnline": True},
        {"id": 2, "numEntrants": 40, "videogame": {"id": 1386}, "teamRosterSize": None},
        {"id": 3, "numEntrants": 70, "videogame": {"id": 1}, "teamRosterSize": None},
        {
            "id": 4,
            "numEntrants": 20,
            "videogame": {"id": 1386},
            "teamRosterSize": {"maxPlayers": 2},
        },
        {"id": 5, "numEntrants": 12, "videogame": {"id": 1386}},
    ]
    assert singles_event({"events": events})["id"] == 2
    assert singles_event({"events": events[2:4]}) is None


def test_preview_projects_seeds_and_finds_crossings():
    from uuid import uuid4

    from app.insights import preview

    hub = {str(n): uuid4() for n in range(1, 10)}  # start.gg ids 1..9 are in the hub
    tags = {hub[k]: f"P{k}" for k in hub}
    data = Data(tags=tags)
    # P1 beat P8 three times, P3 and P5 met three times, P4 is on a 3-set streak.
    data.matches = [match(i, hub["1"], hub["8"]) for i in range(3)]
    data.matches += [
        match(10 + i, hub["3" if i else "5"], hub["5" if i else "3"]) for i in range(3)
    ]
    data.matches += [match(20 + i, hub["4"], hub["9"]) for i in range(3)]
    entrants = [{"startgg_player_id": k, "gamer_tag": f"P{k}"} for k in [*hub, "99"]]
    order = {k: int(k) for k in hub if k != "9"}  # official seeds; 9 and 99 not in it
    result = preview.build(
        data,
        tournament={"name": "Open", "slug": "tournament/open", "startAt": 1794920400},
        event={"name": "Singles"},
        entrants=entrants,
        ids=hub,
        order=order,
        source={"source": "seeding", "label": "Seeding oficial"},
    )
    assert [p["tag"] for p in result["entrants"]] == [*(f"P{i}" for i in range(1, 10)), "P99"]
    assert result["entrants"][-1]["id"] is None
    assert result["tournament"]["slug"] == "open"
    assert result["tournament"]["starts_at"].startswith("2026-11-17")
    assert [p["tag"] for p in result["favorites"]] == ["P1", "P2", "P3", "P4"]
    # Same streak: the better seed first.
    assert [(p["tag"], p["streak"]) for p in result["on_fire"]] == [("P1", 3), ("P4", 3)]
    first = result["crossings"][0]
    assert (first["stage"], first["a"]["tag"], first["b"]["tag"]) == (
        "Cuartos de winners",
        "P1",
        "P8",
    )
    assert (first["h2h"]["a_wins"], first["h2h"]["b_wins"]) == (3, 0)
    assert next(c for c in result["crossings"] if c["a"]["seed"] == 4)["h2h"] is None
    # P1-P8 is already a crossing, so it is not repeated among the rivalries.
    assert [(r["a"]["tag"], r["b"]["tag"], r["sets"]) for r in result["rivalries"]] == [
        ("P3", "P5", 3),
        ("P4", "P9", 3),
    ]
    assert result["newcomers"] == {"count": 4, "tags": ["P2", "P6", "P7", "P99"]}

    # Without a published official seeding there are no seeds, favorites or crossings.
    unofficial = preview.build(
        data,
        tournament={"name": "Open", "slug": "tournament/open"},
        event={"name": "Singles"},
        entrants=entrants,
        ids=hub,
        order={},
        source={"source": "none", "label": "Sin seeding"},
    )
    assert all(p["seed"] is None for p in unofficial["entrants"])
    assert unofficial["favorites"] == [] and unofficial["crossings"] == []
    assert [(p["tag"], p["streak"]) for p in unofficial["on_fire"]] == [("P1", 3), ("P4", 3)]
    assert [(r["a"]["tag"], r["sets"]) for r in unofficial["rivalries"]][0] == ("P1", 3)


def provider_set(n, *, me_won, entrants=100, placement=5, online=False, day=10, country="MX"):
    """A start.gg set node between player 7 ("Chag") and an opponent."""
    ts = int(datetime(2026, 9, day, 20, tzinfo=UTC).timestamp())
    return {
        "id": n,
        "state": 3,
        "completedAt": ts,
        "winnerId": 1 if me_won else 2,
        "displayScore": "2 - 1",
        "event": {
            "id": 500 + day,
            "numEntrants": entrants,
            "isOnline": online,
            "startAt": ts,
            "videogame": {"id": 1386},
            "tournament": {
                "name": f"Open {day}",
                "slug": f"tournament/open-{day}",
                "countryCode": country,
            },
        },
        "slots": [
            {
                "entrant": {
                    "id": 1,
                    "name": "ISG | Chag",
                    "standing": {"placement": placement},
                    "participants": [{"player": {"id": 7}}],
                },
                "standing": {"stats": {"score": {"value": 2 if me_won else 1}}},
            },
            {
                "entrant": {
                    "id": 2,
                    "name": "Rival",
                    "standing": {"placement": 9},
                    "participants": [{"player": {"id": 8}}],
                },
                "standing": {"stats": {"score": {"value": 1 if me_won else 2}}},
            },
        ],
    }


def test_visitor_summary_from_startgg_sets():
    from app.insights.visitors import summarize

    nodes = [
        provider_set(1, me_won=True, day=10, placement=1, entrants=150),
        provider_set(2, me_won=True, day=10, placement=1, entrants=150),
        provider_set(3, me_won=False, day=20, placement=5, entrants=343, country="SV"),
        provider_set(4, me_won=True, day=25, online=True),  # online: not counted
        provider_set(5, me_won=True, day=26, placement=2, entrants=40),
    ]
    result = summarize(
        nodes,
        7,
        start=datetime(2025, 10, 1, tzinfo=UTC),
        end=datetime(2026, 10, 1, tzinfo=UTC),
        mains=[{"character": "Min Min", "icon": None, "games": 9, "share": 90.0}],
    )
    assert (result["tag"], result["country"]) == ("ISG | Chag", "MX")
    assert (result["wins"], result["losses"], result["tournaments"]) == (3, 1, 3)
    assert [e["tournament"] for e in result["recent"]] == ["Open 26", "Open 20", "Open 10"]
    assert [(e["placement"], e["entrants"]) for e in result["best"]] == [
        (1, 150),
        (2, 40),
        (5, 343),
    ]
    assert result["recent"][0]["url"] == "https://www.start.gg/tournament/open-26"
    assert result["mains"][0]["character"] == "Min Min"
