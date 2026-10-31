"""Tournaments being played, read from start.gg (Mission 27). Synthetic data only."""

import time

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.startgg.client import ImportFailure
from app.live import router as live_router
from app.live import service
from app.main import create_app

NOW = 1_800_000_000


def tournament(**changes):
    data = {
        "name": "SaN's",
        "slug": "tournament/sans",
        "startAt": NOW - 3600,
        "isOnline": False,
        "city": "Ciudad del Este",
        "events": [
            {
                "id": 1,
                "name": "Amateur",
                "numEntrants": 40,
                "state": "ACTIVE",
                "videogame": {"id": 1386},
            },
            {
                "id": 2,
                "name": "Singles",
                "numEntrants": 16,
                "state": "ACTIVE",
                "videogame": {"id": 1386},
            },
            {"id": 3, "name": "Mario Kart", "videogame": {"id": 9}},
        ],
    }
    return data | changes


def entrant(id, tag=None, prefix=None):
    return {
        "id": id,
        "name": tag or f"P{id}",
        "participants": [
            {"gamerTag": tag or f"P{id}", "prefix": prefix, "player": {"id": 100 + id}}
        ],
    }


def slot(id=None, score=None, seed=None, prereq=None, placement=1, **extra):
    return {
        "entrant": entrant(id, **extra) if id else None,
        "seed": {"seedNum": seed} if seed else None,
        "standing": {"stats": {"score": {"value": score}}} if score is not None else None,
        "prereqType": "set" if prereq else "seed",
        "prereqId": prereq,
        "prereqPlacement": placement if prereq else None,
    }


def result(id, round, *slots, state=3, winner=None, label="Winners Round 1", games=None):
    return {
        "id": id,
        "round": round,
        "state": state,
        "winnerId": winner,
        "fullRoundText": label,
        "completedAt": NOW if state == 3 else None,
        "slots": list(slots),
        "games": games,
    }


def raw(sets, *, state="ACTIVE", standings=()):
    t = tournament()
    return dict(
        tournament=t,
        events=service.singles(t),
        event=t["events"][1],
        groups=[dict(id="g", name="Bracket", type="DOUBLE_ELIMINATION", sets=sets)],
        standings={"state": state, "standings": {"nodes": list(standings)}},
    )


def build(data, **kwargs):
    return service.build(
        data, approve=lambda p: "BG" if p == "bg" else None, hub={"101": "hub-1"}, **kwargs
    )


def test_main_event_first_and_only_ultimate_singles():
    assert [e["name"] for e in service.singles(tournament())] == ["Singles", "Amateur"]


def test_listed_shows_what_is_on_or_just_ended():
    finished = [dict(e, state="COMPLETED") if "state" in e else e for e in tournament()["events"]]
    nodes = [
        tournament(),
        tournament(slug="tournament/just-ended", events=finished, startAt=NOW - 7200),
        tournament(slug="tournament/old", events=finished, startAt=NOW - 50 * 3600),
        tournament(slug="tournament/two-days", startAt=NOW - 50 * 3600),
        tournament(slug="tournament/soon", startAt=NOW + 3600),
        tournament(slug="tournament/online", isOnline=True),
    ]
    assert [(t["slug"], t["active"]) for t in service.listed(nodes, NOW)] == [
        ("sans", True),
        ("just-ended", False),
        ("two-days", True),
    ]


def test_a_set_in_play_shows_its_score_so_far_and_the_empty_ones_wait():
    pick = lambda e, name: {"entrant": {"id": e}, "character": {"name": name}}  # noqa: E731
    data = raw(
        [
            result(
                10,
                1,
                slot(1, 2, seed=1, prefix="bg"),
                slot(2, 0, seed=8, prefix="chiste"),
                winner=1,
                games=[
                    {"orderNum": 1, "winnerId": 1, "selections": [pick(1, "Ken"), pick(2, "Ryu")]}
                ],
            ),
            result(11, 1, slot(3, seed=4), slot(4, seed=5), state=2),
            result(12, 2, slot(1, prereq=10), slot(prereq=11), state=1, label="Winners Final"),
            result(13, 1, slot(5, 0, seed=2), slot(), winner=5),  # a bye
        ]
    )
    live = build(data)
    assert live["final"] is False and live["current"] == "g"
    first, second = live["groups"][0]["winners"]
    done, running = first["sets"]
    assert done["status"] == "played" and running["status"] == "live"
    p1, p2 = done["sides"]
    assert (p1["tag"], p1["prefix"], p1["id"], p1["score"], p1["winner"]) == (
        "P1",
        "BG",
        "hub-1",
        2,
        True,
    )
    assert p2["prefix"] is None  # not approved
    assert p1["characters"] == [{"name": "Ken", "icon": None}]
    assert done["games"][0]["winner"] == 1
    assert second["label"] == "Final de winners"
    waiting = second["sets"][0]
    assert waiting["status"] == "pending"
    assert [s["tag"] for s in waiting["sides"]] == ["P1", None]
    assert len(first["sets"]) == 2  # the bye is not listed


def test_disqualifications_keep_their_mark():
    live = build(raw([result(10, 1, slot(1, 0), slot(2, -1), winner=1)]))
    match = live["groups"][0]["winners"][0]["sets"][0]
    assert match["status"] == "dq"
    assert match["sides"][1]["score"] is None


def grand_final(winner, **changes):
    return result(
        20,
        3,
        slot(1, 3, prereq=18),
        slot(2, 1, prereq=19),
        winner=winner,
        label="Grand Final",
        **changes,
    )


def finals(*extra):
    return [
        result(18, 2, slot(1, 3), slot(3, 0), winner=1, label="Winners Final"),
        result(19, -2, slot(2, 3), slot(3, 0), winner=2, label="Losers Final"),
        *extra,
    ]


def test_top_is_final_when_grand_finals_are_decided():
    groups = lambda sets: [dict(sets=sets)]  # noqa: E731
    assert not service.decided(groups(finals()), "ACTIVE")
    # The player from winners wins: no reset, even if start.gg has not closed the event.
    assert service.decided(groups(finals(grand_final(1))), "ACTIVE")
    # The player from losers wins: the reset is still to play.
    assert not service.decided(groups(finals(grand_final(2))), "ACTIVE")
    reset = result(21, 4, slot(1, 1), slot(2, 3), winner=2, label="Grand Final Reset")
    assert service.decided(groups(finals(grand_final(2), reset)), "ACTIVE")
    assert service.decided(groups(finals()), "COMPLETED")


def test_unused_reset_is_hidden():
    reset = result(
        21, 4, slot(prereq="20"), slot(prereq="20", placement=2), state=1, label="Grand Final Reset"
    )
    live = build(raw(finals(grand_final(1), reset)))
    assert live["final"] is True
    labels = [c["label"] for c in live["groups"][0]["winners"]]
    assert labels == ["Final de winners", "Gran final"]


def test_phases_nobody_reached_are_left_out_and_top_lists_mains():
    data = raw(
        [result(10, 1, slot(1, 2), slot(2, 0), winner=1)],
        standings=[
            {"placement": 1, "entrant": dict(entrant(2), initialSeedNum=3)},
            {"placement": 2, "entrant": dict(entrant(1, prefix="bg"), initialSeedNum=1)},
        ],
    )
    data["groups"].append(
        dict(
            id="top8",
            name="Top 8",
            type="DOUBLE_ELIMINATION",
            sets=[result(30, 1, slot(), slot(), state=1)],
        )
    )
    known = {"102": [dict(character="Zelda", icon=None, games=4, share=100.0)]}
    live = build(data, known_mains=known, costumes={"102": {"Zelda": 3}})
    assert [g["id"] for g in live["groups"]] == ["g"]
    first, second = live["top"]
    assert (first["tag"], first["seed"], first["placement"]) == ("P2", 3, 1)
    assert first["mains"][0]["character"] == "Zelda" and first["mains"][0]["costume"] == 3
    assert (second["prefix"], second["id"]) == ("BG", "hub-1")


def client(db):
    return TestClient(
        create_app(
            Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/x"),
            engine=db,
        )
    )


class FakeClient:
    fail = False
    reads = 0

    def __init__(self, token):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, document, variables):
        return {"tournaments": {"nodes": [tournament(startAt=int(time.time()) - 60)]}}


def test_only_listed_tournaments_are_read_and_a_failure_keeps_the_last_reading(db, monkeypatch):
    monkeypatch.setattr(live_router, "StartGGClient", FakeClient)
    monkeypatch.setattr(live_router, "_list", {"at": -999, "items": None})
    monkeypatch.setattr(live_router, "_events", {})
    reads = []

    def payload(request, slug, event):
        reads.append(slug)
        if len(reads) > 1:
            raise ImportFailure("startgg_unavailable")
        return dict(final=False, groups=[])

    monkeypatch.setattr(live_router, "payload", payload)
    with client(db) as c:
        assert [t["slug"] for t in c.get("/api/v1/live").json()["items"]] == ["sans"]
        assert c.get("/api/v1/live/otro-torneo").status_code == 404
        assert reads == []
        assert c.get("/api/v1/live/sans").json() == {"final": False, "groups": []}
        c.get("/api/v1/live/sans")
        assert reads == ["sans"]  # cached for every visitor
        key = ("sans", None)
        live_router._events[key] = (-999, live_router._events[key][1])
        assert c.get("/api/v1/live/sans").json()["stale"] is True
        assert c.get("/api/v1/live/Bad_Slug").status_code == 422
