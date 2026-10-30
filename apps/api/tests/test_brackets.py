"""Brackets of past events and the projected one of an upcoming event (Mission 25)."""

import copy

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_startgg import prepare, run
from test_startgg import snapshot as snapshot

from app.brackets import layout, service
from app.brackets import router as brackets_router
from app.competitions.models import Event, Set
from app.core.config import Settings
from app.main import create_app


def node(id, round, *feeds, shown=True, label=None):
    return dict(
        id=id,
        round=round,
        label=label,
        shown=shown,
        prereqs=[(f, place) for f, place in feeds],
    )


def test_sets_sit_between_the_sets_that_feed_them():
    nodes = [
        node("a", 1),
        node("b", 1),
        node("bye", 1, shown=False),
        node("c", 1),
        node("ab", 2, ("a", 1), ("b", 1)),
        node("c2", 2, ("bye", 1), ("c", 1)),
        node("final", 3, ("ab", 1), ("c2", 1), label="Winners Final"),
        # Losers: the drop-ins (placement 2) do not shape the tree.
        node("l1", -1, ("a", 2), ("b", 2)),
        node("l2", -2, ("l1", 1), ("ab", 2), label="Losers Final"),
    ]
    laid = layout.arrange(nodes)
    rows = {s["id"]: s["row"] for c in laid["winners"] for s in c["sets"]}
    assert rows == {"a": 0, "b": 1, "c": 2, "ab": 0.5, "c2": 2, "final": 1.25}
    to = {s["id"]: s["to"] for c in laid["winners"] for s in c["sets"]}
    assert to == {"a": "ab", "b": "ab", "c": "c2", "ab": "final", "c2": "final", "final": None}
    assert [c["label"] for c in laid["winners"]][-1] == "Final de winners"
    assert [[s["id"] for s in c["sets"]] for c in laid["losers"]] == [["l1"], ["l2"]]
    assert laid["losers"][1]["label"] == "Final de losers"
    assert laid["height"] == 3


def test_round_names_and_seed_positions():
    assert layout.round_label("Winners Round 2") == "Winners ronda 2"
    assert layout.round_label("Grand Final Reset") == "Gran final (reset)"
    assert layout.round_label("Round 3") == "Ronda 3"
    assert layout.seed_order(8) == [1, 8, 4, 5, 2, 7, 3, 6]


def test_projection_follows_the_published_seeds():
    people = [dict(seed=n, tag=f"P{n}", id=None, mains=[]) for n in range(1, 7)]
    people[0]["mains"] = [dict(character="Ryu", icon="https://x/ryu.png")]
    bracket = service.projected(people)
    columns = bracket["groups"][0]["winners"]
    assert [c["label"] for c in columns] == [
        "Cuartos de winners",
        "Semifinal de winners",
        "Final de winners",
    ]
    # Seeds 1 and 2 have byes: only 4-5 and 3-6 play the first round.
    first = [[side["seed"] for side in s["sides"]] for s in columns[0]["sets"]]
    assert first == [[4, 5], [3, 6]]
    semis = [[side["seed"] for side in s["sides"]] for s in columns[1]["sets"]]
    assert semis == [[1, 4], [2, 3]]
    assert columns[1]["sets"][0]["sides"][0]["characters"] == [
        dict(name="Ryu", icon="https://x/ryu.png")
    ]
    assert columns[2]["sets"][0]["status"] == "projected"
    assert service.projected(people[:3]) is None


class FakeClient:
    calls = 0

    def __init__(self, token):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, document, variables):
        assert document == "event_phases"
        FakeClient.calls += 1
        return {
            "event": {
                "phases": [
                    {
                        "name": "Top 8",
                        "phaseOrder": 2,
                        "phaseGroups": {"nodes": [{"id": 72, "displayIdentifier": "1"}]},
                    },
                    {
                        "name": "Bracket",
                        "phaseOrder": 1,
                        "phaseGroups": {"nodes": [{"id": 71, "displayIdentifier": "1"}]},
                    },
                ]
            }
        }


def bracket_set(id, round, group, *feeds, label="Winners Round 1"):
    return {
        "id": id,
        "state": 3,
        "round": round,
        "fullRoundText": label,
        "completedAt": 1700000000 + id,
        "updatedAt": 1700000001,
        "winnerId": 11,
        "displayScore": "2 - 0",
        "phaseGroup": {"id": group, "bracketType": "DOUBLE_ELIMINATION"},
        "slots": [
            {
                "entrant": {"id": entrant},
                "standing": {"stats": {"score": {"value": score}}},
                **(
                    {
                        "prereqType": "set",
                        "prereqId": str(feeds[i][0]),
                        "prereqPlacement": feeds[i][1],
                    }
                    if feeds
                    else {}
                ),
            }
            for i, (entrant, score) in enumerate(((11, 2), (12, 0)))
        ],
    }


def test_event_bracket_reads_phase_names_once(db, snapshot, monkeypatch):
    prepare(db)
    source = copy.deepcopy(snapshot)
    source["events"][0]["sets"] = [
        bracket_set(2001, 1, 71),
        bracket_set(2002, 2, 71, (2001, 1), (2001, 2), label="Grand Final"),
        bracket_set(2003, 1, 72, label="Winners Final"),
    ]
    run(db, source)
    with Session(db) as s:
        event_id = s.scalar(select(Set.event_id).where(Set.round_label == "Grand Final"))
    FakeClient.calls = 0
    monkeypatch.setattr(brackets_router, "StartGGClient", FakeClient)
    with TestClient(
        create_app(
            Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/x"),
            engine=db,
        )
    ) as c:
        body = c.get(f"/api/v1/events/{event_id}/bracket").json()
        assert [g["name"] for g in body["groups"]] == ["Bracket", "Top 8"]
        first = body["groups"][0]["winners"]
        assert [c["label"] for c in first] == ["Winners ronda 1", "Gran final"]
        opener, final = first[0]["sets"][0], first[1]["sets"][0]
        assert opener["to"] == final["id"] == "2002"
        assert opener["row"] == final["row"] == 0
        assert [(side["tag"], side["score"], side["winner"]) for side in opener["sides"]] == [
            ("Same", 2, True),
            ("Same", 0, False),
        ]
        assert opener["sides"][0]["id"]
        c.get(f"/api/v1/events/{event_id}/bracket")
        assert FakeClient.calls == 1  # stored after the first visit
        assert c.get("/api/v1/events/not-a-uuid/bracket").status_code == 422
    with Session(db) as s:
        assert service.phase_names(s.get(Event, event_id).phases)["72"]["name"] == "Top 8"


def pool_set(id, round, *slots, label="Winners Round 1"):
    return dict(id=id, round=round, fullRoundText=label, slots=list(slots))


def by_seed(n):
    return dict(seed={"seedNum": n}, prereqType="seed", prereqId=f"seed{n}")


def from_set(id, n=None):
    # start.gg names the seed coming from a bye on the next round's slot.
    return dict(
        prereqType="set", prereqId=id, prereqPlacement=1, seed={"seedNum": n} if n else None
    )


def test_pools_from_startgg_take_the_hubs_seeds():
    found = dict(
        later=["TOP 8"],
        groups=[
            dict(
                id="g1",
                name="Pools · 1",
                sets=[
                    pool_set("p1-1", 1, by_seed(4), by_seed(5)),
                    pool_set("p1-2", 2, from_set("bye", 1), from_set("p1-1")),
                    pool_set("p1-l", -1, from_set("p1-1")),
                ],
            ),
            dict(
                id="g2",
                name="Pools · 2",
                sets=[pool_set("p2-1", 1, by_seed(2), by_seed(3))],
            ),
        ],
    )
    people = [dict(seed=n, tag=f"P{n}", id=None, mains=[]) for n in range(1, 6)]
    result = service.seeded(found, people)
    assert result["source"] == "startgg" and result["later"] == ["TOP 8"]
    assert [g["name"] for g in result["groups"]] == ["Pools · 1", "Pools · 2"]
    pool = result["groups"][0]
    assert pool["losers"] == []
    cells = [[[x["tag"] for x in s["sides"]] for s in c["sets"]] for c in pool["winners"]]
    assert cells == [[["P4", "P5"]], [["P1", "P4"]]]


def test_first_phase_is_where_everyone_is_seeded():
    data = {
        "event": {
            "phases": [
                {"id": 3, "name": "TOP 8", "phaseOrder": 3, "numSeeds": 0},
                {"id": 4, "name": "Pools", "phaseOrder": 4, "numSeeds": 77},
            ]
        }
    }
    assert service.first_phase(data)["name"] == "Pools"
    assert service.first_phase({"event": {"phases": []}}) is None


def test_bracket_preview_is_for_organizers_only(db):
    with TestClient(
        create_app(
            Settings(
                _env_file=None,
                database_url="postgresql://unused:unused@localhost/x",
                admin_token="secret-key-for-tests-only-0123",
            ),
            engine=db,
        )
    ) as c:
        assert c.get("/api/v1/seeding/cs/bracket").status_code == 401
        missing = c.get(
            "/api/v1/seeding/cs/bracket",
            headers={"Authorization": "Bearer secret-key-for-tests-only-0123"},
        )
        assert missing.status_code == 404
