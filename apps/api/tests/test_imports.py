"""Mission 06: character selections, mains and web imports. Never calls start.gg."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_startgg import prepare, run
from test_startgg import snapshot as snapshot

from app.competitions.models import Set, SetSelection
from app.core.config import Settings
from app.games.models import Character
from app.integrations.models import ExternalMapping
from app.integrations.startgg import bulk
from app.main import create_app
from app.players.models import ExternalIdentity

KEY = "k" * 32
AUTH = {"Authorization": f"Bearer {KEY}", "X-Admin-Name": "Org"}


def games(*picks):
    """picks: (winner entrant, character of 11, character of 12) per game."""
    return [
        {
            "orderNum": n,
            "winnerId": winner,
            "selections": [
                {"entrant": {"id": 11}, "character": {"id": c11, "name": f"C{c11}"}},
                {"entrant": {"id": 12}, "character": {"id": c12, "name": f"C{c12}"}},
            ],
        }
        for n, (winner, c11, c12) in enumerate(picks, 1)
    ]


def client_for(db):
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
    )
    return TestClient(create_app(settings, engine=db))


def test_selections_are_stored_without_changing_result_fingerprints(db, snapshot):
    prepare(db)
    run(db, snapshot)
    with Session(db) as s:
        hashes = dict(
            s.execute(
                select(ExternalMapping.external_id, ExternalMapping.payload_hash).where(
                    ExternalMapping.entity_type == "set"
                )
            ).all()
        )
    final = snapshot["events"][0]["sets"][0]
    final["games"] = games((11, 1, 2), (11, 1, 3))
    summary = run(db, snapshot)
    with Session(db) as s:
        rows = s.execute(
            select(SetSelection.game_number, Character.name, SetSelection.won)
            .join(Character)
            .order_by(SetSelection.game_number, Character.name)
        ).all()
        assert [tuple(r) for r in rows] == [
            (1, "C1", True),
            (1, "C2", False),
            (2, "C1", True),
            (2, "C3", False),
        ]
        assert s.scalar(select(func.count()).select_from(Character)) == 3
        after = dict(
            s.execute(
                select(ExternalMapping.external_id, ExternalMapping.payload_hash).where(
                    ExternalMapping.entity_type == "set"
                )
            ).all()
        )
        assert after == hashes  # Selections never rewrite results or their history.
        assert all(not m.result_history for m in s.scalars(select(Set)))
    assert summary["counts"]["updated"] == 0
    # A correction replaces the selections; re-importing the same ones is a no-op.
    final["games"] = games((11, 4, 2))
    run(db, snapshot)
    run(db, snapshot)
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(SetSelection)) == 2


def test_mains_in_player_list_and_detail(db, snapshot):
    prepare(db)
    snapshot["events"][0]["sets"][0]["games"] = games((11, 1, 2), (11, 1, 2), (12, 5, 2))
    run(db, snapshot)
    with Session(db) as s:
        # Entrant 11 is start.gg player 100.
        player = s.scalar(
            select(ExternalIdentity.player_id).where(ExternalIdentity.external_id == "player:100")
        )
    with client_for(db) as client:
        items = client.get("/api/v1/players?page_size=100").json()["items"]
        listed = next(i for i in items if i["id"] == str(player))
        assert [m["character"] for m in listed["mains"]] == ["C1", "C5"]
        detail = client.get(f"/api/v1/players/{player}").json()
        assert detail["mains"] == [
            {"character": "C1", "games": 2, "share": 66.7},
            {"character": "C5", "games": 1, "share": 33.3},
        ]


def test_web_import_requires_admin_and_reports_progress(db, monkeypatch):
    calls = []

    def fake_runner(engine, token, actor, **kwargs):
        calls.append(kwargs)
        bulk._update(status="completed", total=1, done=1)
        bulk._record(dict(slug="t", name="T", status="completed", counts={}, conflicts=0))

    monkeypatch.setattr(bulk, "_state", {"status": "idle"})
    original = bulk.start
    monkeypatch.setattr(bulk, "start", lambda *a, **k: original(*a, **k, runner=fake_runner))
    with client_for(db) as client:
        body = {
            "country": "PY",
            "window_start": "2025-11-14T00:00:00-03:00",
            "end": "2026-11-14T00:00:00-03:00",
        }
        assert client.post("/api/v1/imports/startgg", json=body).status_code == 401
        # Without STARTGG_API_TOKEN nothing starts.
        r = client.post("/api/v1/imports/startgg", json=body, headers=AUTH)
        assert r.status_code == 422
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        startgg_api_token="t",
    )
    with TestClient(create_app(settings, engine=db)) as client:
        r = client.post("/api/v1/imports/startgg", json=body, headers=AUTH)
        assert r.status_code == 202
        assert calls[0]["country"] == "PY" and calls[0]["slugs"] is None
        state = client.get("/api/v1/imports/status", headers=AUTH).json()
        assert state["status"] == "completed" and state["results"][0]["status"] == "completed"
        links = {"source": "links", "urls": ["https://www.start.gg/tournament/abc/details"]}
        assert client.post("/api/v1/imports/startgg", json=links, headers=AUTH).status_code == 202
        assert calls[1]["slugs"] == ["abc"]
        bad = {"source": "links", "urls": ["https://evil.example/x"]}
        assert client.post("/api/v1/imports/startgg", json=bad, headers=AUTH).status_code == 422
