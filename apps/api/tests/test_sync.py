"""Local copy of start.gg and its sync (SH-SYNC-01, ADR-022). Synthetic data only."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from accounts import LEGACY_EXPIRES
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.startgg.client import ImportFailure
from app.main import create_app
from app.sync import read, service
from app.sync.models import (
    StartggEntrant,
    StartggEntrantMember,
    StartggSyncRun,
    StartggTournament,
)

KEY = "s" * 32
AUTH = {"Authorization": f"Bearer {KEY}", "X-Admin-Name": "Org"}
NOW = datetime.now(UTC)
START = int((NOW + timedelta(days=3)).timestamp())


def entrant(eid, player, tag, *, seed=None, prefix=None):
    return dict(
        id=eid,
        name=tag,
        initialSeedNum=seed,
        participants=[
            dict(
                id=f"p{eid}",
                gamerTag=tag,
                prefix=prefix,
                player={"id": player} if player else None,
                user={"location": {"country": "Paraguay"}},
            )
        ],
    )


def tournament_node():
    return dict(
        id=900,
        name="Center Stage 2026",
        slug="tournament/center-stage-2026",
        startAt=START,
        endAt=START + 36000,
        state=1,
        city="Asunción",
        countryCode="PY",
        venueName="Club",
        numAttendees=4,
        isOnline=False,
        images=[{"type": "banner", "url": "https://images.start.gg/b.png"}],
        events=[
            dict(
                id=500,
                name="Ultimate Singles",
                slug="tournament/center-stage-2026/event/singles",
                numEntrants=4,
                isOnline=False,
                startAt=START,
                state="CREATED",
                teamRosterSize=None,
                videogame={"id": 1386},
            ),
            dict(
                id=501,
                name="Doubles",
                slug="tournament/center-stage-2026/event/doubles",
                numEntrants=2,
                isOnline=False,
                startAt=START,
                state="CREATED",
                teamRosterSize={"maxPlayers": 2},
                videogame={"id": 1386},
            ),
        ],
    )


class FakeStartGG:
    """start.gg as the sync sees it: one tournament, its singles entrants."""

    def __init__(self):
        self.tournament = tournament_node()
        self.entrants = {
            "500": [
                entrant(1, 10, "Ace", seed=1),
                entrant(2, 20, "Bee", seed=2, prefix="KZN"),
                entrant(3, 30, "Cid"),
                entrant(4, None, "Invitado"),  # no start.gg account: never matched by tag
            ]
        }
        self.fail = set()
        self.calls = []
        self.calendar = [tournament_node()]

    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, document, variables):
        self.calls.append(document)
        if document in self.fail:
            raise ImportFailure("startgg_transport_error")
        if document == "sync_tournament":
            slug = "tournament/" + variables["slug"]
            return {
                "tournament": deepcopy(self.tournament) if slug == self.tournament["slug"] else None
            }
        if document == "upcoming_tournaments":
            return {"tournaments": {"nodes": deepcopy(self.calendar)}}
        raise AssertionError(document)

    async def pages(self, document, root, connection, external_id, *, variables=None, per_page=10):
        self.calls.append(document)
        if document in self.fail:
            raise ImportFailure("startgg_incomplete_pagination")
        if document == "sync_entrants":
            return deepcopy(self.entrants.get(str(external_id), []))
        raise AssertionError(document)


def settings(**extra):
    values = dict(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        admin_token_expires=LEGACY_EXPIRES,
        startgg_api_token=SecretStr("t"),
    )
    return Settings(**(values | extra))


def sync(db, fake, slug="center-stage-2026", trigger="auto"):
    run_id = service.claim(db, kind="tournament", trigger=trigger, actor="test", slug=slug)
    error = service.run_tournament(db, settings(), run_id, slug, client_factory=fake)
    with Session(db) as s:
        return s.get(StartggSyncRun, run_id), error


def active_tags(db, event_id="500"):
    with Session(db) as s:
        return sorted(e["gamer_tag"] for e in read.singles_entrants(s, event_id))


# ------------------------------------------------------------------ schedule (no database)


def at(days=0, hours=0):
    return NOW + timedelta(days=days, hours=hours)


@pytest.mark.parametrize(
    ("start", "state", "expected"),
    [
        (at(days=30), 1, "far"),
        (at(days=5), 1, "week"),
        (at(hours=10), 1, "day"),
        (at(hours=1), 1, "live"),  # doors open two hours before
        (at(days=5), 2, "live"),  # start.gg says it already started
        (at(days=-1, hours=-7), 1, "finished"),
        (at(days=3), 3, "finished"),
    ],
)
def test_tiers_follow_how_close_the_tournament_is(start, state, expected):
    row = SimpleNamespace(start_at=start, end_at=None, state=state)
    assert service.tier(row, NOW) == expected


def test_next_sync_uses_the_tier_frequency_and_backs_off_on_failures():
    conf = settings(startgg_sync_live_seconds=120)
    live = SimpleNamespace(start_at=at(hours=1), end_at=at(hours=9), state=1, failures=0)
    assert service.next_sync(live, NOW, conf, failed=False) == NOW + timedelta(seconds=120)
    live.failures = 3  # 5 min, 10, 20: never hammering start.gg while it fails
    assert service.next_sync(live, NOW, conf, failed=True) == NOW + timedelta(minutes=20)
    gone = SimpleNamespace(start_at=at(days=-9), end_at=at(days=-8), state=3, failures=0)
    assert service.next_sync(gone, NOW, conf, failed=False) is None


def test_sync_settings_are_bounded():
    with pytest.raises(ValueError):
        settings(startgg_sync_live_seconds=5)
    with pytest.raises(ValueError):
        settings(startgg_sync_request_interval=0.1)


# ------------------------------------------------------------------ registrations


def test_sync_copies_tournament_events_and_registrations(db):
    fake = FakeStartGG()
    run, error = sync(db, fake)
    assert error is None and run.status == "completed"
    assert run.counts["entrants_created"] == 4 and run.counts["events_created"] == 2
    with Session(db) as s:
        t = s.get(StartggTournament, "900")
        assert (t.slug, t.country_code, t.track_reason) == ("center-stage-2026", "PY", "manual")
        assert t.last_status == "completed" and t.failures == 0
        assert t.next_sync_at > NOW  # three days ahead: the "week" frequency
        ace = s.scalar(select(StartggEntrantMember).where(StartggEntrantMember.gamer_tag == "Ace"))
        assert (ace.participant_id, ace.player_id, ace.entrant_id) == ("p1", "10", "1")
        local = read.upcoming(s, "center-stage-2026")
    # Doubles are listed but only the singles event's registrations are copied.
    assert "sync_entrants" in fake.calls and fake.calls.count("sync_entrants") == 1
    assert local["event"]["id"] == "500"
    bee = next(e for e in local["entrants"] if e["gamer_tag"] == "Bee")
    assert bee == dict(
        startgg_entrant_id="2",
        startgg_player_id="20",
        gamer_tag="Bee",
        prefix="KZN",
        profile_country="Paraguay",
    )
    # The guest without a start.gg player is stored but never offered for matching.
    assert active_tags(db) == ["Ace", "Bee", "Cid"]


def test_withdrawals_are_marked_and_returns_reactivate(db):
    fake = FakeStartGG()
    sync(db, fake)
    fake.entrants["500"] = [e for e in fake.entrants["500"] if e["name"] != "Cid"]
    run, _ = sync(db, fake)
    assert run.counts["entrants_retired"] == 1
    assert active_tags(db) == ["Ace", "Bee"]
    with Session(db) as s:
        cid = s.get(StartggEntrant, "3")
        assert cid.active is False and cid.removed_at is not None  # kept, not deleted
    fake.entrants["500"].append(entrant(3, 30, "Cid"))
    sync(db, fake)
    assert active_tags(db) == ["Ace", "Bee", "Cid"]
    with Session(db) as s:
        assert s.get(StartggEntrant, "3").removed_at is None


def test_an_empty_answer_never_wipes_registrations(db):
    fake = FakeStartGG()
    sync(db, fake)
    fake.entrants["500"] = []
    run, _ = sync(db, fake)
    assert run.status == "completed" and run.warnings == ["empty_entrants_kept:500"]
    assert active_tags(db) == ["Ace", "Bee", "Cid"]


def test_a_failed_sync_keeps_the_local_copy_and_is_logged(db):
    fake = FakeStartGG()
    sync(db, fake)
    fake.fail.add("sync_entrants")
    run, error = sync(db, fake)
    assert error == "startgg_incomplete_pagination"
    assert (run.status, run.error_code) == ("failed", "startgg_incomplete_pagination")
    with Session(db) as s:
        t = s.get(StartggTournament, "900")
        assert (t.last_status, t.failures, t.last_error) == (
            "failed",
            1,
            "startgg_incomplete_pagination",
        )
        assert t.last_success_at is not None  # the previous success stays recorded
    assert active_tags(db) == ["Ace", "Bee", "Cid"]


def test_unknown_tournament_is_logged_without_a_row(db):
    run, error = sync(db, FakeStartGG(), slug="does-not-exist")
    assert error == "startgg_tournament_not_found"
    assert (run.slug, run.tournament_id, run.status) == ("does-not-exist", None, "failed")


# ------------------------------------------------------------------ one sync at a time


def test_only_one_sync_runs_at_a_time(db):
    first = service.claim(db, kind="tournament", trigger="auto", actor="a", slug="x")
    with pytest.raises(service.SyncBusy):
        service.claim(db, kind="discovery", trigger="manual", actor="b")
    # A run left "running" by a dead process stops blocking after a while.
    later = datetime.now(UTC) + service.STALE_RUN + timedelta(minutes=1)
    service.claim(db, kind="discovery", trigger="auto", actor="c", now=later)
    with Session(db) as s:
        dead = s.get(StartggSyncRun, first)
        assert (dead.status, dead.error_code) == ("failed", "abandoned")


def test_a_seeding_download_in_progress_blocks_the_sync(db):
    from app.seeding.models import SeedingProject

    with Session(db) as s:
        s.add(
            SeedingProject(
                slug="cs",
                name="CS",
                startgg_event_id="500",
                startgg_event_slug="tournament/center-stage-2026/event/singles",
                startgg_videogame_id="1386",
                event_date=NOW + timedelta(days=3),
                window_start=NOW - timedelta(days=200),
                refresh_status="RUNNING",
                refresh_started_at=NOW,
            )
        )
        s.commit()
    with pytest.raises(service.SyncBusy, match="seeding"):
        service.claim(db, kind="tournament", trigger="auto", actor="a", slug="x")


# ------------------------------------------------------------------ scheduler


def test_tick_discovers_the_calendar_then_syncs_what_is_due(db):
    fake = FakeStartGG()
    service.tick(db, settings(), client_factory=fake)
    assert fake.calls[:2] == ["upcoming_tournaments", "sync_tournament"]
    with Session(db) as s:
        t = s.get(StartggTournament, "900")
        assert (t.in_calendar, t.track_reason, t.last_status) == (True, "calendar", "completed")
        runs = s.scalars(select(StartggSyncRun).order_by(StartggSyncRun.started_at)).all()
        assert [(r.kind, r.status) for r in runs] == [
            ("discovery", "completed"),
            ("tournament", "completed"),
        ]
    # Nothing is due right after: a second tick asks start.gg nothing.
    fake.calls.clear()
    service.tick(db, settings(), client_factory=fake)
    assert fake.calls == []
    # Gone from start.gg's upcoming list: off the calendar, data kept.
    fake.calendar = []
    run_id = service.claim(db, kind="discovery", trigger="manual", actor="t")
    service.run_discovery(db, settings(), run_id, client_factory=fake)
    with Session(db) as s:
        assert s.get(StartggTournament, "900").in_calendar is False
    assert active_tags(db) == ["Ace", "Bee", "Cid"]


def test_seeding_tournaments_are_synced_even_off_the_calendar(db):
    from app.seeding.models import SeedingProject

    with Session(db) as s:
        s.add(
            SeedingProject(
                slug="cs",
                name="CS",
                startgg_event_id="500",
                startgg_event_slug="tournament/center-stage-2026/event/singles",
                startgg_videogame_id="1386",
                event_date=NOW + timedelta(days=3),
                window_start=NOW - timedelta(days=200),
            )
        )
        s.commit()
    assert service.due(db, settings()) == [("center-stage-2026", "seeding")]
    fake = FakeStartGG()
    fake.calendar = []
    service.tick(db, settings(), client_factory=fake)
    with Session(db) as s:
        assert s.get(StartggTournament, "900").track_reason == "seeding"


def test_scheduler_stays_off_unless_enabled(db):
    from app.sync.scheduler import maybe_start

    assert maybe_start(db, settings()) is None
    assert maybe_start(db, settings(startgg_sync_enabled=True, startgg_api_token=None)) is None


# ------------------------------------------------------------------ pages read the copy


def client_for(db, **extra):
    return TestClient(create_app(settings(**extra), engine=db))


def test_preview_reads_the_local_copy_when_startgg_is_down(db, monkeypatch):
    from app.insights import router

    sync(db, FakeStartGG())

    class Down:
        def __init__(self, *args, **kwargs):
            raise AssertionError("a synced preview must not ask start.gg")

    monkeypatch.setattr(router, "StartGGClient", Down)
    with client_for(db) as client:
        body = client.get("/api/v1/insights/upcoming/center-stage-2026").json()
    assert body["tournament"]["name"] == "Center Stage 2026"
    assert body["event"] == {"name": "Ultimate Singles", "entrants": 3}
    assert sorted(p["tag"] for p in body["entrants"]) == ["Ace", "Bee", "Cid"]
    assert body["startgg"]["source"] == "local" and body["startgg"]["synced_at"]


def test_calendar_reads_the_local_copy_after_a_discovery(db, monkeypatch):
    from app.insights import router

    fake = FakeStartGG()
    run_id = service.claim(db, kind="discovery", trigger="manual", actor="t")
    service.run_discovery(db, settings(), run_id, client_factory=fake)
    monkeypatch.setattr(router, "StartGGClient", None)  # never called
    with client_for(db) as client:
        body = client.get("/api/v1/insights/calendar").json()
    assert [i["name"] for i in body["items"]] == ["Center Stage 2026"]
    assert body["items"][0]["event"]["slug"] == "tournament/center-stage-2026/event/singles"
    assert body["items"][0]["images"] == {"banner": "https://images.start.gg/b.png"}
    assert body["synced_at"]


# ------------------------------------------------------------------ administrators


def test_manual_sync_is_for_administrators_and_reports_status(db, monkeypatch):
    from app.sync import router

    fake = FakeStartGG()
    monkeypatch.setattr(
        router,
        "_start",
        lambda target, *args: target(*args, client_factory=fake),
    )
    with client_for(db) as client:
        body = {"tournament": "https://www.start.gg/tournament/center-stage-2026"}
        assert client.post("/api/v1/sync/tournaments", json=body).status_code == 401
        assert client.get("/api/v1/sync").status_code == 401
        r = client.post("/api/v1/sync/tournaments", json=body, headers=AUTH)
        assert r.status_code == 202 and r.json()["slug"] == "center-stage-2026"
        bad = client.post("/api/v1/sync/tournaments", json={"tournament": "a b"}, headers=AUTH)
        assert bad.status_code == 422
        status = client.get("/api/v1/sync", headers=AUTH).json()
        assert status["enabled"] is False
        row = status["tournaments"][0]
        assert (row["slug"], row["tracked"], row["last_status"]) == (
            "center-stage-2026",
            True,
            "completed",
        )
        run = status["runs"][0]
        assert (run["trigger"], run["actor"], run["status"]) == ("manual", "clave:Org", "completed")
        assert run["counts"]["entrants_created"] == 4
        off = client.put(
            "/api/v1/sync/tournaments/center-stage-2026/tracking",
            json={"tracked": False},
            headers=AUTH,
        )
        assert off.json() == {"slug": "center-stage-2026", "tracked": False}
    with Session(db) as s:
        assert s.get(StartggTournament, "900").next_sync_at is None
