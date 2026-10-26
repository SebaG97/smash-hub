"""Seeding (Mission 05). Automated tests never call start.gg."""

import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.main import create_app
from app.seeding import service, startgg
from app.seeding.engine import apply_overrides, compute
from app.seeding.models import SeedingAuditEntry, SeedingProject

KEY = "k" * 32
START = datetime(2026, 1, 1, tzinfo=UTC)
EVENT = datetime(2026, 6, 1, tzinfo=UTC)
ENTRANTS = [
    dict(player_id=p, gamer_tag=t)
    for p, t in (("1", "Ace"), ("2", "Bee"), ("3", "Cid"), ("4", "Dot"), ("5", "Eve"))
]


def a_set(
    n,
    winner,
    loser,
    *,
    day=10,
    online=False,
    event="e1",
    entrants=16,
    places=(1, 2),
    counted=True,
    country="PY",
):
    return dict(
        startgg_set_id=str(n),
        played_at=START + timedelta(days=day),
        startgg_event_id=event,
        tournament_name=f"T {event}",
        tournament_slug=None,
        event_entrants=entrants,
        online=online,
        country=country,
        p1_player_id=winner,
        p1_tag=winner,
        p1_placement=places[0],
        p2_player_id=loser,
        p2_tag=loser,
        p2_placement=places[1],
        winner_player_id=winner,
        classification="played" if counted else "dq",
        counted=counted,
    )


def dataset():
    sets = []
    n = 0
    for week in range(8):
        for w, losers in (("1", "234"), ("2", "34"), ("3", "4")):
            for loser in losers:
                n += 1
                sets.append(
                    a_set(
                        n, w, loser, day=7 * week + 1, event=f"e{week}", places=(int(w), int(loser))
                    )
                )
    sets.append(a_set(999, "3", "9", day=20, event="e2"))  # 9 is a merged ID of player 4
    sets.append(a_set(1000, "1", "2", day=200))  # outside window
    sets.append(a_set(1001, "2", "1", counted=False))  # DQ never counts
    return sets


def test_compute_orders_explains_and_respects_window_and_merges():
    rows, summary = compute(
        ENTRANTS, dataset(), merges={"9": "4"}, duplicates={}, window_start=START, window_end=EVENT
    )
    assert [r["gamer_tag"] for r in rows] == ["Ace", "Bee", "Cid", "Dot", "Eve"]
    assert summary["set_count"] == 8 * 6 + 1
    ace, dot, eve = rows[0], rows[3], rows[4]
    assert (ace["wins"], ace["losses"]) == (24, 0)
    assert dot["merged_sets"] == 1 and any("fusionados" in f for f in dot["flags"])
    assert eve["combined"] is None and eve["flags"] == ["sin datos: ubicar manualmente"]
    assert any("Glicko-2" in r for r in ace["reasons"]) and any(
        "Posiciones" in r for r in ace["reasons"]
    )


def test_duplicates_are_excluded_and_overrides_pin_seeds():
    rows, _ = compute(
        ENTRANTS, dataset(), merges={}, duplicates={"5": "1"}, window_start=START, window_end=EVENT
    )
    assert "5" not in {r["player_id"] for r in rows}
    final = apply_overrides(
        rows,
        [
            dict(player_id="3", seed=1, reason="r", actor="a"),
            dict(player_id="1", seed=99, reason="r", actor="a"),
        ],
    )
    assert [r["gamer_tag"] for r in final] == ["Cid", "Bee", "Dot", "Ace"]
    assert [r["seed"] for r in final] == [1, 2, 3, 4]
    assert final[0]["override"]["reason"] == "r" and final[1]["override"] is None


def node(
    sid,
    *,
    game=1386,
    event=7,
    ts=None,
    state=3,
    scores=(3, 1),
    players=("1", "2"),
    winner=1,
    dq=False,
):
    slots = [
        {
            "entrant": {
                "id": i + 1,
                "name": p,
                "standing": {"placement": i + 1},
                "participants": [{"player": {"id": p}}],
            },
            "standing": {"stats": {"score": {"value": s}}},
        }
        for i, (p, s) in enumerate(zip(players, scores, strict=True))
    ]
    return {
        "id": sid,
        "state": state,
        "completedAt": ts or int((START + timedelta(days=3)).timestamp()),
        "winnerId": winner,
        "displayScore": "DQ" if dq else "3 - 1",
        "hasPlaceholder": False,
        "event": {
            "id": event,
            "numEntrants": 32,
            "isOnline": False,
            "startAt": None,
            "videogame": {"id": game},
            "tournament": {"name": "T", "slug": "tournament/t", "countryCode": "PY"},
        },
        "slots": slots,
    }


def test_normalize_filters_scope_and_classifies():
    nodes = [
        node(1),
        node(1),
        node(2, game=1),
        node(3, event=99),
        node(4, dq=True),
        node(5, ts=int((EVENT + timedelta(days=1)).timestamp())),
        node(6, scores=(None, None)),
    ]
    rows, excluded = startgg.normalize(
        nodes, videogame_id="1386", own_event_id="99", start=START, end=EVENT
    )
    assert {r["startgg_set_id"]: r["classification"] for r in rows} == {
        "1": "played",
        "4": "dq",
        "6": "played_unscored",
    }
    assert excluded == {"other_game": 1, "seeded_event": 1, "outside_window": 1}
    assert rows[0]["winner_player_id"] == "1" and rows[0]["counted"]


# ---------------------------------------------------------------- PostgreSQL + HTTP


@pytest.fixture
def project(db):
    with Session(db) as session:
        p = SeedingProject(
            slug="cs",
            name="Center",
            startgg_event_id="99",
            startgg_event_slug="tournament/t/event/e",
            startgg_videogame_id="1386",
            event_date=EVENT,
            window_start=START,
            merges={"9": "4"},
            duplicates={},
        )
        session.add(p)
        session.flush()
        service.replace_dataset(
            session,
            p,
            [
                dict(
                    startgg_entrant_id=f"x{e['player_id']}",
                    startgg_player_id=e["player_id"],
                    gamer_tag=e["gamer_tag"],
                )
                for e in ENTRANTS
            ],
            dataset(),
            cutoff=EVENT - timedelta(days=5),
        )
        session.flush()
        service.recalculate(session, p, "test")
        session.commit()
    return db


def client_for(db, admin_token=KEY, token=None):
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=admin_token,
        startgg_api_token=token,
    )
    return TestClient(create_app(settings, engine=db))


AUTH = {"Authorization": f"Bearer {KEY}", "X-Admin-Name": "Org <script>"}


def test_view_is_public_and_explains_data(project):
    with client_for(project) as client:
        body = client.get("/api/v1/seeding/cs").json()
        assert [s["gamer_tag"] for s in body["seeds"]][:2] == ["Ace", "Bee"]
        assert body["dataset"]["entrants"] == 5 and body["run"]["window_start"].startswith(
            "2026-01-01"
        )
        assert body["merges"] == [{"from_player_id": "9", "to_player_id": "4", "tag": "Dot"}]
        assert client.get("/api/v1/seeding").json()[0]["slug"] == "cs"
        assert client.get("/api/v1/seeding/nope").status_code == 404


def test_writes_require_admin_key(project):
    with client_for(project) as client:
        assert client.post("/api/v1/seeding/cs/recalculate", json={}).status_code == 401
        bad = {"Authorization": "Bearer " + "x" * 32}
        assert (
            client.put(
                "/api/v1/seeding/cs/overrides/3", json={"seed": 1, "reason": "test"}, headers=bad
            ).status_code
            == 401
        )
    with client_for(project, admin_token=None) as client:
        assert (
            client.post("/api/v1/seeding/cs/recalculate", json={}, headers=AUTH).status_code == 503
        )


def test_move_reset_recalculate_export_and_audit(project):
    with client_for(project) as client:
        assert (
            client.get("/api/v1/seeding/cs/session", headers=AUTH).json()["actor"] == "Org script"
        )
        r = client.put(
            "/api/v1/seeding/cs/overrides/3",
            json={"seed": 1, "reason": "conocido local"},
            headers=AUTH,
        )
        assert r.status_code == 200
        seeds = client.get("/api/v1/seeding/cs").json()["seeds"]
        assert seeds[0]["gamer_tag"] == "Cid" and seeds[0]["override"]["actor"] == "Org script"
        assert (
            client.put(
                "/api/v1/seeding/cs/overrides/3", json={"seed": 50, "reason": "xxx"}, headers=AUTH
            ).status_code
            == 422
        )
        # Recalculating keeps manual moves and applies a narrower window.
        r = client.post(
            "/api/v1/seeding/cs/recalculate",
            headers=AUTH,
            json={"window_start": "2026-01-20T00:00:00Z"},
        )
        assert r.status_code == 200
        body = client.get("/api/v1/seeding/cs").json()
        assert body["seeds"][0]["gamer_tag"] == "Cid" and body["run"]["set_count"] < 49
        assert (
            client.post(
                "/api/v1/seeding/cs/recalculate",
                headers=AUTH,
                json={"window_start": "2025-01-01T00:00:00Z"},
            ).status_code
            == 422
        )
        exported = client.get("/api/v1/seeding/cs/export.csv")
        rows = list(csv.DictReader(io.StringIO(exported.text.lstrip("﻿"))))
        assert rows[0]["gamer_tag"] == "Cid" and rows[0]["manual"] == "sí"
        assert client.delete("/api/v1/seeding/cs/overrides/3", headers=AUTH).status_code == 200
        assert client.delete("/api/v1/seeding/cs/overrides/3", headers=AUTH).status_code == 422
        actions = [e["action"] for e in client.get("/api/v1/seeding/cs/audit", headers=AUTH).json()]
        assert actions[:4] == ["reset", "recalculate", "move", "recalculate"]


def test_refresh_replaces_dataset_and_recalculates(project, monkeypatch):
    async def fake_download(engine, project_id, client, start):
        entrants = [
            dict(startgg_entrant_id="x1", startgg_player_id="1", gamer_tag="Ace"),
            dict(startgg_entrant_id="x2", startgg_player_id="2", gamer_tag="Bee"),
        ]
        return entrants, [a_set(1, "2", "1")], {"other_game": 3}, EVENT - timedelta(days=1)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(service, "_download", fake_download)
    monkeypatch.setattr(service, "StartGGClient", FakeClient)
    with client_for(project, token=SecretStr("t")) as client:
        app = client.app
        monkeypatch.setattr(
            service.threading,
            "Thread",
            lambda target, args, **kw: type("T", (), {"start": lambda self: target(*args)})(),
        )
        r = client.post("/api/v1/seeding/cs/recalculate", json={"refresh": True}, headers=AUTH)
        assert r.status_code == 202
        body = client.get("/api/v1/seeding/cs").json()
        assert body["refresh"]["status"] == "IDLE"
        assert [s["gamer_tag"] for s in body["seeds"]] == ["Bee", "Ace"]
        assert app is not None
    with Session(project) as session:
        actions = session.scalars(select(SeedingAuditEntry.action)).all()
        assert "refresh_completed" in actions


def test_refresh_requires_token_and_is_single_flight(project):
    with client_for(project) as client:
        r = client.post("/api/v1/seeding/cs/recalculate", json={"refresh": True}, headers=AUTH)
        assert r.status_code == 422
    with Session(project) as session:
        p = session.scalar(select(SeedingProject))
        p.refresh_status, p.refresh_started_at = "RUNNING", datetime.now(UTC)
        session.commit()
    with client_for(project, token=SecretStr("t")) as client:
        r = client.post("/api/v1/seeding/cs/recalculate", json={"refresh": True}, headers=AUTH)
        assert r.status_code == 409
        assert (
            client.post("/api/v1/seeding/cs/recalculate", json={}, headers=AUTH).status_code == 422
        )
