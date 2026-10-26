import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.communities.service import bootstrap
from app.competitions.models import (
    Event,
    EventEntrant,
    Set,
    SetSide,
    Tournament,
    TournamentParticipant,
)
from app.core.config import Settings
from app.integrations.models import ExternalMapping, ImportJob
from app.integrations.startgg.client import ENDPOINT, ImportFailure, StartGGClient, parse_slug
from app.integrations.startgg.service import run_import, validate
from app.main import create_app
from app.players.models import ExternalIdentity, Player, PlayerAlias

FIXTURE = Path(__file__).parent / "fixtures" / "startgg.json"


@pytest.fixture
def snapshot():
    return json.loads(FIXTURE.read_text())


class FixtureClient:
    def __init__(self, data):
        self.data = data

    async def download(self, slug):
        return copy.deepcopy(self.data)


def run(db, data, **kwargs):
    return asyncio.run(run_import(db, FixtureClient(data), "fixture-open", **kwargs))


def prepare(db):
    with Session(db) as s, s.begin():
        bootstrap(s)


@pytest.mark.parametrize(
    "value",
    [
        "fixture-open",
        "tournament/fixture-open",
        "https://www.start.gg/tournament/fixture-open/?a=1#events",
        "https://start.gg:443/tournament/fixture-open",
    ],
)
def test_slug(value):
    assert parse_slug(value) == "fixture-open"


@pytest.mark.parametrize(
    "value",
    [
        "http://start.gg/tournament/x",
        "https://start.gg.evil/tournament/x",
        "https://evil/start.gg/tournament/x",
        "https://start.gg@evil/tournament/x",
        "https://user@start.gg/tournament/x",
        "https://start.gg:8000/tournament/x",
        "https://start.gg/tournament/%2e%2e",
        "file:///etc/passwd",
        "//localhost",
        "https://127.0.0.1/tournament/x",
        "https://start.gg/tournament/x/event/y",
        "x?token=secret",
        "x\\evil",
        "https://start.gg/tournament/x%0d%0a",
    ],
)
def test_malicious_urls(value):
    with pytest.raises(ImportFailure):
        parse_slug(value)


def test_token_optional_startup_but_required_for_client():
    settings = Settings(_env_file=None, database_url="postgresql://u:p@localhost/x")
    assert settings.startgg_api_token is None
    with pytest.raises(ImportFailure, match="startgg_token_missing"):
        StartGGClient(None)


@pytest.mark.parametrize(
    "kind", ["http", "graphql", "partial", "redirect", "json", "transport", "rate", "provider_rate"]
)
def test_http_errors_and_retry(kind):
    requests, delays = [], []

    async def sleep(value):
        delays.append(value)

    def handler(req):
        requests.append(req)
        assert str(req.url) == ENDPOINT
        if kind == "transport":
            raise httpx.ReadTimeout("SECRET", request=req)
        if kind == "json":
            return httpx.Response(200, text="not json")
        if kind == "redirect":
            return httpx.Response(302, headers={"location": "http://localhost/SECRET"})
        if kind in {"rate", "provider_rate"} and len(requests) < 3:
            return (
                httpx.Response(429, headers={"Retry-After": "2"})
                if kind == "rate"
                else httpx.Response(
                    200, json={"success": False, "message": "Rate limit exceeded - api-token"}
                )
            )
        if kind in {"rate", "provider_rate"}:
            return httpx.Response(200, json={"data": {"ok": True}})
        if kind in {"graphql", "partial"}:
            return httpx.Response(
                200,
                json={
                    "errors": [{"message": "SECRET"}],
                    "data": {"tournament": {"id": 1}} if kind == "partial" else None,
                },
            )
        return httpx.Response(503, text="SECRET")

    async def exercise():
        async with StartGGClient(
            SecretStr("TEST_ONLY"), transport=httpx.MockTransport(handler), sleep=sleep
        ) as client:
            if kind in {"rate", "provider_rate"}:
                assert await client.query("tournament", {"slug": "fixture-open"}) == {"ok": True}
                assert len(requests) == 3
                assert any(d >= 2 for d in delays)
            else:
                with pytest.raises(ImportFailure) as exc:
                    await client.query("tournament", {"slug": "fixture-open"})
                assert "SECRET" not in str(exc.value)
                assert len(requests) == (4 if kind in {"http", "transport"} else 1)

    asyncio.run(exercise())


@pytest.mark.parametrize("broken", [None, "duplicate", "short", "total_changed", "null"])
def test_pagination(broken):
    def handler(req):
        page = json.loads(req.content)["variables"]["page"]
        nodes = [{"id": i} for i in (range(10) if page == 1 else range(10, 12))]
        if broken == "duplicate" and page == 2:
            nodes = [{"id": 0}, {"id": 11}]
        if broken == "short" and page == 2:
            nodes = []
        return httpx.Response(
            200,
            json={
                "data": {
                    "event": {
                        "entrants": None
                        if broken == "null"
                        else {
                            "pageInfo": {
                                "total": 13 if broken == "total_changed" and page == 2 else 12,
                                "totalPages": 2,
                            },
                            "nodes": nodes,
                        }
                    }
                }
            },
        )

    async def exercise():
        async with StartGGClient(
            SecretStr("TEST_ONLY"), transport=httpx.MockTransport(handler), sleep=AsyncMock()
        ) as c:
            if broken:
                with pytest.raises(ImportFailure, match="incomplete_pagination"):
                    await c.pages("entrants", "event", "entrants", "1")
            else:
                assert len(await c.pages("entrants", "event", "entrants", "1")) == 12

    asyncio.run(exercise())


def test_import_idempotent_singles_doubles_multiple_events(db, snapshot):
    prepare(db)
    first = run(db, snapshot)
    second = run(db, snapshot)
    assert first["tournament_id"] == second["tournament_id"]
    assert second["counts"]["created"] == second["counts"]["updated"] == 0
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(Player)) == 4
        assert s.scalar(select(func.count()).select_from(TournamentParticipant)) == 4
        assert s.scalar(select(func.count()).select_from(EventEntrant)) == 4
        assert s.scalar(select(func.count()).select_from(ExternalIdentity)) == 3
        assert s.scalar(select(func.count()).select_from(Player).where(Player.tag == "Same")) == 2
        assert s.scalar(select(func.count()).select_from(Set)) == 6
        assert set(s.scalars(select(Event.team_size))) == {1, 2}
        results = {m.round_label: m for m in s.scalars(select(Set))}
        assert results["Final"].ranking_eligible
        assert results["Pending"].status == "pending"
        assert results["DQ"].status == "dq"
        assert results["BYE"].status == "bye"
        assert results["Missing score"].status == "incomplete"
        assert results["Missing date"].completed_at is None
        for label in ["Pending", "DQ", "BYE", "Missing score"]:
            assert not results[label].ranking_eligible
        assert all(
            score is None
            for score in s.scalars(
                select(SetSide.score).where(SetSide.set_id == results["Pending"].id)
            )
        )


def test_historical_tag_change_across_tournaments(db, snapshot):
    prepare(db)
    run(db, snapshot)
    changed = copy.deepcopy(snapshot)
    changed["tournament"].update(id=200, slug="tournament/new-event")
    for p in changed["participants"]:
        p["id"] += 1000
        if p["player"] and p["player"]["id"] == 100:
            p["gamerTag"] = "New tag"
    # New tournament: singles only, independent event/entrant IDs.
    changed["events"] = changed["events"][:1]
    event = changed["events"][0]
    event["id"] = 30
    changed["tournament"]["events"] = [{"id": 30}]
    event["sets"], event["standings"] = [], []
    for i, entrant in enumerate(event["entrants"]):
        entrant["id"] += 100
        entrant["participants"] = [changed["participants"][i]]
    result = run(db, changed)
    with Session(db) as s:
        assert (
            s.scalar(select(func.count()).select_from(Player)) == 5
        )  # unverified identity remains scoped
        identity = s.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_id == "player:100")
        )
        tags = set(
            s.scalars(select(PlayerAlias.tag).where(PlayerAlias.player_id == identity.player_id))
        )
        assert tags == {"Same", "New tag"}
        assert (
            s.scalar(
                select(TournamentParticipant.tag_snapshot).where(
                    TournamentParticipant.tournament_id
                    == __import__("uuid").UUID(result["tournament_id"]),
                    TournamentParticipant.player_id == identity.player_id,
                )
            )
            == "New tag"
        )


def test_result_corrections_manual_locks_and_tag_preservation(db, snapshot):
    prepare(db)
    run(db, snapshot)
    snapshot["events"][0]["sets"][0]["slots"][0]["standing"]["stats"]["score"]["value"] = 3
    run(db, snapshot)
    with Session(db) as s, s.begin():
        match = s.scalar(select(Set).where(Set.round_label == "Final"))
        assert len(match.result_history) == 1
        match.manual_locked = True
        player = s.scalar(
            select(Player)
            .join(ExternalIdentity)
            .where(ExternalIdentity.external_id == "player:100")
        )
        player.tag, player.manual_locked = "Manual", True
    snapshot["events"][0]["sets"][0]["slots"][0]["standing"]["stats"]["score"]["value"] = 4
    snapshot["participants"][0]["gamerTag"] = "Changed"
    for event in snapshot["events"]:
        for entrant in event["entrants"]:
            for p in entrant["participants"]:
                if p["id"] == 1:
                    p["gamerTag"] = "Changed"
    result = run(db, snapshot)
    assert {x["code"] for x in result["conflicts"]} >= {
        "manual_correction_preserved",
        "historical_tag_preserved",
    }
    with Session(db) as s:
        match = s.scalar(select(Set).where(Set.round_label == "Final"))
        assert match.source_result["slots"][0]["standing"]["stats"]["score"]["value"] == 3
        assert (
            s.scalar(
                select(Player.tag)
                .join(ExternalIdentity)
                .where(ExternalIdentity.external_id == "player:100")
            )
            == "Manual"
        )
        assert (
            s.scalar(
                select(TournamentParticipant.tag_snapshot)
                .join(
                    ExternalIdentity, ExternalIdentity.player_id == TournamentParticipant.player_id
                )
                .where(ExternalIdentity.external_id == "player:100")
            )
            == "Same"
        )


def test_identity_conflict_rolls_back_and_records(db, snapshot):
    prepare(db)
    run(db, snapshot)
    snapshot["participants"][0]["player"]["id"] = 101
    for event in snapshot["events"]:
        for entrant in event["entrants"]:
            for p in entrant["participants"]:
                if p["id"] == 1:
                    p["player"]["id"] = 101
    with pytest.raises(ImportFailure, match="identity_conflict"):
        run(db, snapshot)
    with Session(db) as s:
        job = s.scalar(select(ImportJob).order_by(ImportJob.started_at.desc()))
        assert job.status == "failed" and job.conflicts[0]["code"] == "identity_conflict"
        assert s.scalar(select(func.count()).select_from(Player)) == 4
        assert s.scalar(select(Tournament.published))


def test_failure_mid_persistence_is_atomic_then_retry(db, snapshot, monkeypatch):
    from app.integrations.startgg.service import Persister

    prepare(db)
    original = Persister.mapped

    def broken(self, kind, *args):
        if kind == "set":
            raise RuntimeError("SECRET")
        return original(self, kind, *args)

    with monkeypatch.context() as context:
        context.setattr(Persister, "mapped", broken)
        with pytest.raises(ImportFailure, match="import_validation_or_storage_error"):
            run(db, snapshot)
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(Tournament)) == 0
        assert s.scalar(select(func.count()).select_from(Player)) == 0
        assert s.scalar(select(ImportJob.status)) == "failed"
    run(db, snapshot)


def test_download_failure_preserves_old_published_data(db, snapshot):
    prepare(db)
    run(db, snapshot)
    snapshot["events"][0]["numEntrants"] = 100
    with pytest.raises(ImportFailure, match="incomplete_entrant_list"):
        run(db, snapshot)
    with Session(db) as s:
        assert s.scalar(select(Tournament.published))
        assert s.scalar(select(Event.num_entrants).where(Event.team_size == 1)) == 2


def test_empty_events_and_preview(db, snapshot):
    preview = run(db, snapshot, dry_run=True)
    assert preview["participants"] == 4
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(ImportJob)) == 0
    snapshot["events"], snapshot["tournament"]["events"] = [], []
    with pytest.raises(ImportFailure, match="no_valid_events"):
        validate(snapshot)


def test_same_tournament_lock(db, snapshot):
    prepare(db)
    with db.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(hashtextextended('startgg:fixture-open',0))"))
        conn.commit()
        try:
            with pytest.raises(ImportFailure, match="already_running"):
                run(db, snapshot)
        finally:
            conn.execute(
                text("SELECT pg_advisory_unlock(hashtextextended('startgg:fixture-open',0))")
            )
            conn.commit()


def test_public_endpoints_and_visibility(db, snapshot):
    prepare(db)
    result = run(db, snapshot)
    app = create_app(
        Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/x"), engine=db
    )
    with TestClient(app) as c:
        tournaments = c.get("/api/v1/tournaments?page_size=1").json()
        assert tournaments["total"] == 1
        t = tournaments["items"][0]
        assert t["participant_count"] == 4 and t["entrant_count"] == 4
        assert t["source"] == "start.gg"
        assert c.get(f"/api/v1/tournaments/{t['id']}").status_code == 200
        events = c.get(f"/api/v1/tournaments/{t['id']}/events").json()["items"]
        for e in events:
            assert c.get(f"/api/v1/events/{e['id']}").status_code == 200
            entrants = c.get(f"/api/v1/events/{e['id']}/entrants").json()
            assert len(entrants["items"][0]["members"]) == e["team_size"]
            assert c.get(f"/api/v1/events/{e['id']}/sets").status_code == 200
        players = c.get("/api/v1/players?q=Same").json()
        assert players["total"] == 2
        detail = c.get(f"/api/v1/players/{players['items'][0]['id']}").json()
        assert detail["history"]["total"] == 2
        assert "external_id" not in json.dumps(detail)
        assert c.get("/api/v1/players?page_size=101").status_code == 422
        assert c.post("/api/v1/tournaments", json={}).status_code == 405
        assert c.get("/api/v1/tournaments?q=missing").json()["total"] == 0
        assert c.get("/api/v1/tournaments?page=2").json()["items"] == []
        for path in [
            "tournaments",
            "tournaments/{}/events",
            "players",
            "events",
            "events/{}/sets",
            "events/{}/entrants",
        ]:
            url = (
                path.format("00000000-0000-0000-0000-000000000000")
                if "{}" in path
                else path + "/00000000-0000-0000-0000-000000000000"
            )
            assert c.get("/api/v1/" + url).status_code == 404
        with Session(db) as s, s.begin():
            t = s.get(Tournament, __import__("uuid").UUID(result["tournament_id"]))
            t.published = False
        assert c.get("/api/v1/tournaments").json()["total"] == 0
        assert c.get("/api/v1/players").json()["total"] == 0
        assert c.get(f"/api/v1/events/{events[0]['id']}").status_code == 404


def test_full_http_download_cli_preview_and_persist(db, snapshot, monkeypatch, capsys):
    from app.cli import import_tournament as cli

    prepare(db)
    calls = []

    def handler(req):
        body = json.loads(req.content)
        document = body["query"].split()[1].split("(")[0].lower()
        calls.append(document)
        variables = body["variables"]
        if document == "tournament":
            data = {"tournament": snapshot["tournament"]}
        elif document == "event":
            data = {"event": next(e for e in snapshot["events"] if str(e["id"]) == variables["id"])}
        else:
            root = "tournament" if document == "participants" else "event"
            nodes = (
                snapshot["participants"]
                if document == "participants"
                else next(e for e in snapshot["events"] if str(e["id"]) == variables["id"])[
                    document
                ]
            )
            data = {
                root: {
                    document: {"pageInfo": {"total": len(nodes), "totalPages": 1}, "nodes": nodes}
                }
            }
        return httpx.Response(200, json={"data": data})

    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            database_url="postgresql://u:p@localhost/x",
            environment="test",
            startgg_api_token="TEST_ONLY",
        ),
    )
    monkeypatch.setattr(
        cli,
        "StartGGClient",
        lambda token: StartGGClient(
            token, transport=httpx.MockTransport(handler), sleep=AsyncMock()
        ),
    )
    monkeypatch.setattr(cli, "build_engine", lambda settings: db)
    monkeypatch.setattr(
        "sys.argv",
        ["import_tournament", "--slug", "https://start.gg/tournament/fixture-open", "--dry-run"],
    )
    assert cli.main() == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["status"] == "validated" and preview["sets"] == 6
    assert set(calls) == {"tournament", "event", "participants", "entrants", "standings", "sets"}
    monkeypatch.setattr("sys.argv", ["import_tournament", "--slug", "fixture-open"])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "completed"
    assert "TEST_ONLY" not in json.dumps(result)


def test_cli_bad_slug_missing_token_and_production(monkeypatch, capsys):
    from app.cli import import_tournament as cli

    monkeypatch.setattr("sys.argv", ["import_tournament", "--slug", "https://localhost/evil"])
    assert cli.main() == 1
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_tournament_url"
    monkeypatch.setattr("sys.argv", ["import_tournament", "--slug", "fixture-open"])
    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(_env_file=None, database_url="postgresql://u:p@localhost/x"),
    )
    assert cli.main() == 1
    assert json.loads(capsys.readouterr().out)["error"] == "startgg_token_missing"
    settings = Settings(_env_file=None, database_url="postgresql://u:p@localhost/x")
    settings.environment = "production"
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    assert cli.main() == 1
    assert json.loads(capsys.readouterr().out)["error"] == "production_import_disabled_this_mission"


def test_stale_result_is_not_applied_and_attempts_are_retained(db, snapshot):
    prepare(db)
    run(db, snapshot)
    snapshot["events"][0]["sets"][0]["updatedAt"] -= 1
    snapshot["events"][0]["sets"][0]["slots"][0]["standing"]["stats"]["score"]["value"] = 5
    result = run(db, snapshot)
    assert "stale_source_result" in {c["code"] for c in result["conflicts"]}
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(ImportJob)) == 2
        match = s.scalar(select(Set).where(Set.round_label == "Final"))
        assert match.source_result["slots"][0]["standing"]["stats"]["score"]["value"] == 2


def test_disappeared_historical_records_are_retained(db, snapshot):
    prepare(db)
    run(db, snapshot)
    snapshot["events"][0]["sets"] = []
    run(db, snapshot)
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(Set)) == 6


def test_openapi_snapshot():
    schema = create_app(
        Settings(_env_file=None, database_url="postgresql://u:p@localhost/x")
    ).openapi()
    documented = (Path(__file__).parent / "../../../docs/api/openapi.json").resolve()
    assert schema == json.loads(documented.read_text(encoding="utf8"))


def test_ambiguous_bye_and_double_dq_are_incomplete(db, snapshot):
    prepare(db)
    snapshot["events"][0]["sets"][3]["displayScore"] = None
    snapshot["events"][0]["sets"][3]["slots"][1]["standing"] = {"stats": {"score": {"value": 0}}}
    snapshot["events"][0]["sets"][2]["winnerId"] = None
    snapshot["events"][0]["sets"][2]["slots"][0]["standing"]["stats"]["score"]["value"] = -1
    run(db, snapshot)
    with Session(db) as s:
        assert s.scalar(select(Set.status).where(Set.round_label == "BYE")) == "incomplete"
        assert s.scalar(select(Set.status).where(Set.round_label == "DQ")) == "incomplete"


def test_client_spacing_and_retry_after_limit():
    clock = [0.0]
    calls = []

    async def sleep(delay):
        clock[0] += delay

    def handler(req):
        calls.append(clock[0])
        return httpx.Response(200, json={"data": {"ok": True}})

    async def exercise():
        async with StartGGClient(
            SecretStr("TEST_ONLY"),
            transport=httpx.MockTransport(handler),
            sleep=sleep,
            clock=lambda: clock[0],
        ) as c:
            await c.query("tournament", {})
            await c.query("tournament", {})
            await c.query("tournament", {})
        assert calls == [0, 1, 2]
        async with StartGGClient(
            SecretStr("TEST_ONLY"),
            transport=httpx.MockTransport(
                lambda req: httpx.Response(429, headers={"Retry-After": "600"})
            ),
            sleep=sleep,
        ) as c:
            with pytest.raises(ImportFailure, match="retry_later"):
                await c.query("tournament", {})

    asyncio.run(exercise())


def test_mapping_manual_lock_preserves_entrant(db, snapshot):
    prepare(db)
    run(db, snapshot)
    with Session(db) as s, s.begin():
        mapping = s.scalar(
            select(ExternalMapping).where(
                ExternalMapping.entity_type == "entrant", ExternalMapping.external_id == "11"
            )
        )
        mapping.manual_locked = True
        s.get(EventEntrant, mapping.entrant_id).name = "Corrected by admin"
    snapshot["events"][0]["entrants"][0]["name"] = "Provider update"
    result = run(db, snapshot)
    assert "manual_correction_preserved" in {c["code"] for c in result["conflicts"]}
    with Session(db) as s:
        assert s.scalar(select(EventEntrant.name).where(EventEntrant.name == "Corrected by admin"))


def test_variable_or_unknown_roster_is_not_guessed(snapshot):
    snapshot["events"][1]["teamRosterSize"]["maxPlayers"] = 3
    with pytest.raises(ImportFailure, match="unsupported_variable_roster"):
        validate(snapshot)
    snapshot["events"][1]["teamRosterSize"] = None
    snapshot["events"][1]["name"] = "Singles name is not evidence"
    with pytest.raises(ImportFailure, match="unknown_team_size"):
        validate(snapshot)


def test_three_synthetic_singles_tournaments_share_global_identity(db, snapshot):
    """Synthetic evidence only; never pretend these are authorized real tournaments."""
    prepare(db)
    snapshots = []
    for index in range(3):
        data = copy.deepcopy(snapshot)
        data["events"] = data["events"][:1]
        data["participants"] = data["participants"][:2]
        data["tournament"].update(
            id=300 + index,
            slug=f"tournament/synthetic-{index}",
            startAt=1699900000 + index * 100000,
            endAt=1700100000 + index * 100000,
            events=[{"id": 40 + index}],
        )
        event = data["events"][0]
        event.update(id=40 + index, sets=[], standings=[])
        for offset, person in enumerate(data["participants"]):
            person["id"] = 2000 + index * 10 + offset
            person["gamerTag"] = f"Synthetic tag {index}-{offset}"
            event["entrants"][offset].update(id=3000 + index * 10 + offset, participants=[person])
        snapshots.append(data)
    for data in [snapshots[2], snapshots[0], snapshots[1]]:
        run(db, data)
    with Session(db) as s:
        original_ids = set(s.scalars(select(Player.id)))
        assert len(original_ids) == 2
        assert s.scalar(select(func.count()).select_from(TournamentParticipant)) == 6
        assert s.scalar(select(func.count()).select_from(Event)) == 3
        assert s.scalar(select(func.count()).select_from(PlayerAlias)) == 6
        assert set(s.scalars(select(Player.tag))) == {"Synthetic tag 2-0", "Synthetic tag 2-1"}
    for data in snapshots:
        result = run(db, data)
        assert result["counts"]["created"] == result["counts"]["updated"] == 0
    with Session(db) as s:
        assert set(s.scalars(select(Player.id))) == original_ids


def test_incremental_migration_preserves_legacy_rows(db):
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    with Session(db) as s, s.begin():
        ids = bootstrap(s)
        tournament = Tournament(community_id=ids["community"], slug="legacy", name="Legacy fixture")
        person = Player(tag="Legacy fixture")
        s.add_all([tournament, person])
        s.flush()
        event = Event(
            tournament_id=tournament.id,
            game_id=ids["game"],
            slug="legacy-event",
            name="Legacy fixture",
        )
        s.add(event)
        s.flush()
        event_id = event.id
    command.downgrade(cfg, "0001")
    with db.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM events WHERE id=:id"), {"id": event_id}) == 1
    command.upgrade(cfg, "head")
    with Session(db) as s:
        assert s.get(Event, event_id).team_size == 1
        assert s.scalar(select(func.count()).select_from(Player)) == 1


def test_downgrade_refuses_loss_of_incomplete_results(db, snapshot):
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy.exc import ProgrammingError

    prepare(db)
    run(db, snapshot)
    with pytest.raises(ProgrammingError, match="Resolve incomplete results"):
        command.downgrade(Config("alembic.ini"), "0001")
    with db.connect() as conn:
        # The whole downgrade is one transaction: a refusal keeps the current head.
        head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == head
        assert (
            conn.scalar(
                text("SELECT count(*) FROM pg_constraint WHERE conname='ck_sets_ranking_candidate'")
            )
            == 1
        )
