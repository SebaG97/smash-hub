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
            {"character": "C1", "icon": None, "games": 2, "share": 66.7, "costume": 1},
            {"character": "C5", "icon": None, "games": 1, "share": 33.3, "costume": 1},
        ]


def test_organizers_choose_the_costume_of_each_main(db, snapshot):
    prepare(db)
    snapshot["events"][0]["sets"][0]["games"] = games((11, 1, 2), (11, 1, 2), (12, 5, 2))
    run(db, snapshot)
    with Session(db) as s:
        player = s.scalar(
            select(ExternalIdentity.player_id).where(ExternalIdentity.external_id == "player:100")
        )
    url = f"/api/v1/players/{player}/costume"
    with client_for(db) as client:
        assert client.put(url, json={"character": "C1", "costume": 4}).status_code == 401
        for body in (
            {"character": "C1", "costume": 9},
            {"character": "C1", "costume": 0},
            {"character": "Nadie", "costume": 2},
        ):
            assert client.put(url, json=body, headers=AUTH).status_code == 422
        missing = "/api/v1/players/00000000-0000-0000-0000-000000000000/costume"
        assert (
            client.put(missing, json={"character": "C1", "costume": 2}, headers=AUTH).status_code
            == 404
        )
        r = client.put(url, json={"character": "C1", "costume": 4}, headers=AUTH)
        assert r.json() == {"character": "C1", "costume": 4}
        mains = client.get(f"/api/v1/players/{player}").json()["mains"]
        assert [(m["character"], m["costume"]) for m in mains] == [("C1", 4), ("C5", 1)]
        # Back to the default costume clears the choice.
        client.put(url, json={"character": "C1", "costume": 1}, headers=AUTH)
        assert client.get(f"/api/v1/players/{player}").json()["mains"][0]["costume"] == 1
    with Session(db) as s:
        from app.players.models import Player

        assert s.get(Player, player).costumes == {}


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


def test_character_icons_sync_from_startgg(db):
    import asyncio

    from app.games.icons import sync_characters

    prepare(db)

    class Client:
        async def query(self, document, variables):
            assert document == "characters" and variables == {"id": "1386"}
            return {
                "videogame": {
                    "characters": [
                        {
                            "id": 1,
                            "name": "C1",
                            "images": [
                                {"type": "icon", "url": "https://images.start.gg/big.png"},
                                {"type": "stockIcon", "url": "https://images.start.gg/c1.png"},
                            ],
                        },
                        {
                            "id": 2,
                            "name": "C2",
                            "images": [{"type": "stockIcon", "url": "https://evil.example/x.png"}],
                        },
                    ]
                }
            }

    with Session(db) as s, s.begin():
        assert asyncio.run(sync_characters(Client(), s)) == 2
    with Session(db) as s:
        icons = dict(s.execute(select(Character.name, Character.image_url)).all())
    # Only start.gg's own image host is trusted.
    assert icons == {"C1": "https://images.start.gg/c1.png", "C2": None}


def test_ranking_checkbox_excludes_tournament_and_recalculates(db, snapshot):
    from test_seeding import END_OF, START_OF, ranking_rows

    from app.competitions.models import Tournament
    from app.seeding import service
    from app.seeding.models import SeedingProject

    prepare(db)
    snapshot["events"][0]["sets"][0]["games"] = games((11, 1, 2))
    run(db, snapshot)
    with Session(db) as s:
        tournament_id = s.scalar(select(Tournament.id))
        event_external = s.scalar(
            select(ExternalMapping.external_id).where(ExternalMapping.entity_type == "event")
        )
        project = SeedingProject(
            slug="rk",
            name="Ranking",
            kind="ranking",
            country_code="PY",
            startgg_videogame_id="1386",
            window_start=START_OF,
            event_date=END_OF,
            merges={},
            duplicates={},
        )
        s.add(project)
        s.flush()
        entrants, rows = ranking_rows(event_external)
        service.replace_dataset(s, project, entrants, rows, cutoff=END_OF)
        s.flush()
        service.recalculate(s, project, "test")
        s.commit()
    with client_for(db) as client:
        before = client.get("/api/v1/seeding/rk", headers=AUTH).json()
        assert before["run"]["set_count"] == 2 and before["excluded_tournaments"] == []
        # Player 100 (entrant 11) has mains from the imported tournament.
        ace = next(r for r in before["seeds"] if r["player_id"] == "100")
        assert ace["mains"][0]["character"] == "C1"
        assert (
            client.put(
                f"/api/v1/tournaments/{tournament_id}/ranking", json={"counts": False}
            ).status_code
            == 401
        )
        r = client.put(
            f"/api/v1/tournaments/{tournament_id}/ranking", json={"counts": False}, headers=AUTH
        )
        assert r.status_code == 200 and r.json()["counts_for_ranking"] is False
        after = client.get("/api/v1/seeding/rk", headers=AUTH).json()
        assert after["run"]["set_count"] == 1
        assert after["excluded_tournaments"] == ["Imported"]
        listed = client.get("/api/v1/tournaments").json()["items"][0]
        assert listed["counts_for_ranking"] is False
