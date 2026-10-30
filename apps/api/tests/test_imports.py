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


def test_character_stats_and_matchups_from_imported_games(db, snapshot):
    from app.insights import engine

    prepare(db)
    snapshot["events"][0]["sets"][0]["games"] = games((11, 1, 2), (11, 1, 2), (12, 5, 2))
    run(db, snapshot)
    engine.invalidate()
    with Session(db) as s:
        player = s.scalar(
            select(ExternalIdentity.player_id).where(ExternalIdentity.external_id == "player:100")
        )
    with client_for(db) as client:
        body = client.get("/api/v1/insights/characters").json()
        assert body["games"] == 3
        assert [(i["character"], i["games"], i["win_rate"]) for i in body["items"]] == [
            ("C2", 3, 33.3),
            ("C1", 2, 100.0),
            ("C5", 1, 0.0),
        ]
        matchups = client.get(f"/api/v1/insights/players/{player}/matchups").json()["items"]
        assert matchups == [{"character": "C2", "games": 3, "wins": 2, "win_rate": 66.7}]
    engine.invalidate()


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
        # Only imported hub events count: "Other" never went through the hub (Mission 20).
        assert before["run"]["set_count"] == 1 and before["excluded_tournaments"] == ["Other"]
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
        assert after["run"]["set_count"] == 0
        assert after["excluded_tournaments"] == ["Imported", "Other"]
        listed = client.get("/api/v1/tournaments").json()["items"][0]
        assert listed["counts_for_ranking"] is False
        client.put(
            f"/api/v1/tournaments/{tournament_id}/ranking", json={"counts": True}, headers=AUTH
        )
        # A secondary bracket (amateur, ladder…) does not count either.
        event = client.get(f"/api/v1/tournaments/{tournament_id}/events").json()["items"]
        singles = next(e for e in event if e["team_size"] == 1)
        assert (singles["main"], singles["main_set"]) == (True, False)
        url = f"/api/v1/events/{singles['id']}/main"
        assert client.put(url, json={"main": False}).status_code == 401
        r = client.put(url, json={"main": False}, headers=AUTH).json()
        assert (r["main"], r["main_set"]) == (False, True)
        after = client.get("/api/v1/seeding/rk", headers=AUTH).json()
        assert after["run"]["set_count"] == 0
        assert after["excluded_tournaments"] == ["Imported · " + singles["name"], "Other"]
        # Back to the automatic rule: the only singles bracket is the main one.
        r = client.put(url, json={"main": None}, headers=AUTH).json()
        assert (r["main"], r["main_set"]) == (True, False)
        assert client.get("/api/v1/seeding/rk", headers=AUTH).json()["run"]["set_count"] == 1


def test_upcoming_preview_endpoint_reads_startgg_entrants(db, snapshot, monkeypatch):
    from app.insights import engine, router

    prepare(db)
    run(db, snapshot)
    engine.invalidate()
    tournament = {
        "id": 1,
        "name": "Center Stage",
        "slug": "tournament/center-stage",
        "startAt": 1794920400,
        "city": "Asunción",
        "events": [
            {
                "id": 77,
                "name": "Ultimate Singles",
                "slug": "tournament/center-stage/event/singles",
                "numEntrants": 2,
                "videogame": {"id": 1386},
            }
        ],
    }
    entrants = [
        {"id": 1, "name": "A", "participants": [{"gamerTag": "A", "player": {"id": 100}}]},
        {"id": 2, "name": "Visita", "participants": [{"gamerTag": "Visita", "player": {"id": 9}}]},
    ]
    calls = []

    class FakeClient:
        def __init__(self, token):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def query(self, name, variables):
            calls.append(name)
            if name == "upcoming_tournament":
                return {"tournament": tournament if variables["slug"] == "center-stage" else None}
            page = {"pageInfo": {"total": 2, "totalPages": 1}, "nodes": entrants}
            return {"event": {"entrants": page}}

    monkeypatch.setattr(router, "StartGGClient", FakeClient)
    monkeypatch.setattr(router, "_previews", {})
    from app.brackets import service as brackets

    # The projected bracket reads start.gg's empty bracket (Mission 25): none here.
    monkeypatch.setattr(brackets, "StartGGClient", FakeClient)
    monkeypatch.setattr(brackets, "_structures", {})
    with client_for(db) as client:
        body = client.get("/api/v1/insights/upcoming/center-stage").json()
        assert body["tournament"]["name"] == "Center Stage"
        assert body["event"] == {"name": "Ultimate Singles", "entrants": 2}
        assert body["seeding"]["source"] == "none"
        tags = [(p["seed"], p["tag"], p["id"] is not None) for p in body["entrants"]]
        assert tags == [(None, "A", True), (None, "Visita", False)]
        assert body["newcomers"]["tags"] == ["Visita"]
        # Cached: a second request does not call start.gg again, but the projection is
        # rebuilt, so publishing or unpublishing a seeding shows up right away.
        from app.insights import preview

        official = ({"9": 1}, dict(source="seeding", label="Seeding oficial publicado"))
        with monkeypatch.context() as patch:
            patch.setattr(preview, "projected_order", lambda s, slug: official)
            body = client.get("/api/v1/insights/upcoming/center-stage").json()
        assert calls.count("upcoming_tournament") == 1
        assert body["seeding"]["source"] == "seeding"
        assert [(p["seed"], p["tag"]) for p in body["entrants"]] == [(1, "Visita"), (2, "A")]
        assert body["bracket"] is None  # start.gg has no bracket and 2 players are too few
        body = client.get("/api/v1/insights/upcoming/center-stage").json()
        assert body["seeding"]["source"] == "none"
        assert client.get("/api/v1/insights/upcoming/nada").status_code == 404
        assert client.get("/api/v1/insights/upcoming/Bad_Slug").status_code == 422
    engine.invalidate()


def test_wrongly_seeded_tournaments_yield_no_seed_records(db, snapshot):
    from app.competitions.models import Tournament
    from app.insights import engine

    prepare(db)
    run(db, snapshot)
    engine.invalidate()
    with Session(db) as s:
        tournament = s.scalar(select(Tournament.id))
    url = f"/api/v1/tournaments/{tournament}/seeding"
    summary = f"/api/v1/insights/tournaments/{tournament}"
    with client_for(db) as client:
        assert client.get(f"/api/v1/tournaments/{tournament}").json()["seeding_reliable"] is True
        before = client.get(summary).json()
        assert client.put(url, json={"reliable": False}).status_code == 401
        r = client.put(url, json={"reliable": False}, headers=AUTH)
        assert r.status_code == 200 and r.json()["seeding_reliable"] is False
        after = client.get(summary).json()
        assert [p["tag"] for p in after["top"]] == [p["tag"] for p in before["top"]]
        assert all(p["seed"] is None for p in after["top"])
        assert after["upsets"] == [] and after["overperformers"] == []
        client.put(url, json={"reliable": True}, headers=AUTH)
        assert client.get(summary).json()["top"] == before["top"]
    engine.invalidate()


def test_startgg_player_endpoint_is_cached_and_validated(monkeypatch):
    from app.insights import router, visitors

    calls = []

    class FakeClient:
        def __init__(self, token):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    async def fake_fetch(client, player_id):
        calls.append(player_id)
        if player_id == "404":
            from app.integrations.startgg.client import ImportFailure

            raise ImportFailure("startgg_player_not_found")
        return {"player_id": player_id, "wins": 1, "losses": 0}

    monkeypatch.setattr(router, "StartGGClient", FakeClient)
    monkeypatch.setattr(visitors, "fetch", fake_fetch)
    monkeypatch.setattr(router, "_visitors", {})
    settings = Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/x")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/insights/startgg-players/70916").json()["wins"] == 1
        client.get("/api/v1/insights/startgg-players/70916")
        assert calls == ["70916"]
        assert client.get("/api/v1/insights/startgg-players/404").status_code == 404
        assert client.get("/api/v1/insights/startgg-players/abc").status_code == 422


def test_tournament_images_come_with_the_import_and_can_be_backfilled(db, snapshot, monkeypatch):
    from app.competitions.models import Tournament
    from app.integrations.startgg import client as startgg_client
    from app.integrations.startgg.images import tournament_images

    assert tournament_images(
        [
            {"type": "banner", "url": "https://b"},
            {"type": "profile", "url": "http://insecure"},
            {"type": "other", "url": "https://x"},
        ]
    ) == {"banner": "https://b"}
    prepare(db)
    run(db, snapshot)
    logo = "https://images.start.gg/images/tournament/100/logo.png"
    with client_for(db) as client:
        listed = client.get("/api/v1/tournaments").json()["items"][0]
        assert listed["images"]["profile"] == logo
        assert listed["images"]["banner"].endswith("/banner.png")
    # Tournaments imported before images were kept: an organizer button reads them.
    with Session(db) as s:
        s.get(Tournament, listed["id"]).images = None
        s.commit()
    asked = []

    class FakeClient:
        def __init__(self, token):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def query(self, name, variables):
            asked.append((name, variables))
            return {"tournament": {"id": 1, "images": [{"type": "profile", "url": logo}]}}

    monkeypatch.setattr(startgg_client, "StartGGClient", FakeClient)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        startgg_api_token="token",
    )
    with TestClient(create_app(settings, engine=db)) as client:
        url = "/api/v1/tournaments/images"
        assert client.post(url).status_code == 401
        r = client.post(url, headers=AUTH).json()
        assert r == {"updated": 1, "checked": 1, "remaining": 0}
        assert asked == [("tournament_images", {"slug": "fixture-open"})]
        assert client.get(f"/api/v1/tournaments/{listed['id']}").json()["images"] == {
            "profile": logo
        }
        # Nothing left to read: start.gg is not asked again.
        assert client.post(url, headers=AUTH).json()["checked"] == 0
        assert len(asked) == 1


def test_prefixes_need_approval_and_make_teams(db, snapshot, monkeypatch):
    from app.competitions.models import Tournament, TournamentParticipant
    from app.teams import router as teams_router
    from app.teams.service import clean_prefix

    assert clean_prefix("  [SP] ") == "SP" and clean_prefix(" | ") is None
    prepare(db)
    snapshot["participants"][0]["prefix"] = "BG"  # an approved team (migration 0015)
    snapshot["participants"][1]["prefix"] = "  [Joke]  "  # never reviewed: not shown
    snapshot["participants"][2]["prefix"] = "g0"  # a misspelt GO
    run(db, snapshot)
    from app.teams.models import TeamPrefix

    with Session(db) as s:  # as migration 0015 seeds them (tests truncate every table)
        s.add_all(TeamPrefix(key=k, status="team", name=k.upper()) for k in ("bg", "go"))
        s.commit()
    with Session(db) as s:
        ids = dict(
            s.execute(select(ExternalIdentity.external_id, ExternalIdentity.player_id)).all()
        )
    bg, joke, go = (str(ids[f"player:{n}"]) for n in (100, 101, 102))

    def prefix_of(client, player):
        return client.get(f"/api/v1/players/{player}").json()["prefix"]

    with client_for(db) as client:
        assert prefix_of(client, bg) == "BG"
        assert client.get(f"/api/v1/players/{bg}").json()["team"] == "bg"
        assert prefix_of(client, joke) is None and prefix_of(client, go) is None
        assert client.get("/api/v1/prefixes").status_code == 401
        review = client.get("/api/v1/prefixes", headers=AUTH).json()
        assert [p["key"] for p in review["items"]][:2] == ["g0", "joke"]  # unreviewed first
        assert review["tournaments_to_read"] == 0
        # Organizers hide the joke and join "g0" to GO.
        r = client.put("/api/v1/prefixes/joke", json={"status": "hidden"}, headers=AUTH)
        assert r.json()["status"] == "hidden"
        bad = client.put("/api/v1/prefixes/g0", json={"status": "alias", "team": "x"}, headers=AUTH)
        assert bad.status_code == 422
        client.put("/api/v1/prefixes/g0", json={"status": "alias", "team": "GO"}, headers=AUTH)
        assert prefix_of(client, joke) is None and prefix_of(client, go) == "GO"
        listed = client.get("/api/v1/players?page_size=100").json()["items"]
        assert {p["id"]: p["prefix"] for p in listed}[go] == "GO"
        teams = {t["key"]: t for t in client.get("/api/v1/teams").json()["items"]}
        assert [m["id"] for m in teams["bg"]["members"]] == [bg]
        assert [m["id"] for m in teams["go"]["members"]] == [go]
        assert client.get("/api/v1/teams/go").json()["name"] == "GO"
        assert client.get("/api/v1/teams/nope").status_code == 404
        # GO cannot stop being a team while "g0" is joined to it.
        r = client.put("/api/v1/prefixes/go", json={"status": "hidden"}, headers=AUTH)
        assert r.status_code == 422

    # Tournaments imported before prefixes were kept: an organizer button reads them.
    with Session(db) as s:
        s.execute(TournamentParticipant.__table__.update().values(prefix=None))
        s.execute(Tournament.__table__.update().values(prefixes_read=False))
        s.commit()

    class FakeClient:
        def __init__(self, token):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def pages(self, document, root, connection, external_id, variables=None):
            assert (document, external_id) == ("participants", "100")
            return [
                dict(p, prefix="BG" if p["id"] == 1 else None) for p in snapshot["participants"]
            ]

    monkeypatch.setattr(teams_router, "StartGGClient", FakeClient)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        startgg_api_token="token",
    )
    with TestClient(create_app(settings, engine=db)) as client:
        assert client.post("/api/v1/prefixes/fetch").status_code == 401
        r = client.post("/api/v1/prefixes/fetch", headers=AUTH).json()
        assert r == {"checked": 1, "with_prefix": 1, "remaining": 0}
        assert prefix_of(client, bg) == "BG" and prefix_of(client, go) is None
