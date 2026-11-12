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


def phase(pid, name, order, groups, *, seeds):
    return dict(
        id=pid,
        name=name,
        phaseOrder=order,
        bracketType="DOUBLE_ELIMINATION",
        numSeeds=seeds,
        seeds={"pageInfo": {"total": seeds}},
        phaseGroups={"nodes": [dict(id=g, displayIdentifier=d) for g, d in groups.items()]},
    )


def seed(sid, num, group, pool_seed, *, entrant_id=None, player=None, tag=None, origin=None):
    return dict(
        id=sid,
        seedNum=num,
        groupSeedNum=pool_seed,
        phaseGroup={"id": group},
        entrant=dict(id=entrant_id, name=tag, participants=[{"player": {"id": player}}])
        if entrant_id
        else None,
        progressionSource=dict(originPlacement=origin[1], originPhaseGroup={"id": origin[0]})
        if origin
        else None,
    )


def a_set(sid, round_, *sides, state=1, winner=None, scores=None):
    return dict(
        id=sid,
        round=round_,
        fullRoundText=f"Round {round_}",
        state=state,
        winnerId=winner,
        completedAt=None,
        displayScore=None,
        slots=[
            dict(
                prereqId=seed_id,
                prereqType="seed",
                prereqPlacement=None,
                seed={"seedNum": num},
                entrant={"id": num} if winner else None,
                standing={"stats": {"score": {"value": scores[i]}}} if scores else None,
            )
            for i, (seed_id, num) in enumerate(sides)
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
                entrant(1, 1, "Ace", seed=1),
                entrant(2, 2, "Bee", seed=2, prefix="KZN"),
                entrant(3, 3, "Cid"),
                entrant(4, None, "Invitado"),  # no start.gg account: never matched by tag
            ]
        }
        # Pools A1 and A2, then a top 2 with each pool's winner.
        self.phases = {
            "500": [
                phase(700, "Pools", 1, {801: "A1", 802: "A2"}, seeds=3),
                phase(701, "Top 2", 2, {803: "1"}, seeds=2),
            ]
        }
        self.seeds = {
            "700": [
                seed(7001, 1, 801, 1, entrant_id=1, player=1, tag="Ace"),
                seed(7002, 2, 802, 1, entrant_id=2, player=2, tag="KZN | Bee"),
                seed(7003, 3, 802, 2, entrant_id=3, player=3, tag="Cid"),
            ],
            "701": [
                seed(7101, 1, 803, 1, origin=(801, 1)),
                seed(7102, 2, 803, 2, origin=(802, 1)),
            ],
        }
        # Pool A2's only set (seeds 2 and 3), and the top 2's final.
        self.sets = {
            "801": [],
            "802": [a_set("preview_802_1_0", 1, (7002, 2), (7003, 3))],
            "803": [a_set("preview_803_1_0", 1, (7101, 1), (7102, 2))],
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
        if document == "event_phases":
            return {
                "event": {"id": variables["id"], "phases": deepcopy(self.phases[variables["id"]])}
            }
        raise AssertionError(document)

    async def pages(self, document, root, connection, external_id, *, variables=None, per_page=10):
        self.calls.append(document)
        if document in self.fail:
            raise ImportFailure("startgg_incomplete_pagination")
        if document == "sync_entrants":
            return deepcopy(self.entrants.get(str(external_id), []))
        if document == "sync_phase_seeds":
            return deepcopy(self.seeds.get(str(external_id), []))
        if document == "sync_phase_group_sets":
            return deepcopy(self.sets.get(str(external_id), []))
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
        (at(days=5), 2, "week"),  # ACTIVE on start.gg, but days away (SH-FIX-01)
        (None, 2, "live"),  # no start time: only then start.gg's state counts
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
        assert (ace.participant_id, ace.player_id, ace.entrant_id) == ("p1", "1", "1")
        local = read.upcoming(s, "center-stage-2026")
    # Doubles are listed but only the singles event's registrations are copied.
    assert "sync_entrants" in fake.calls and fake.calls.count("sync_entrants") == 1
    assert local["event"]["id"] == "500"
    bee = next(e for e in local["entrants"] if e["gamer_tag"] == "Bee")
    assert bee == dict(
        startgg_entrant_id="2",
        startgg_player_id="2",
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


# ------------------------------------------------------------------ seeds and pools


def local_pools(db, slug="tournament/center-stage-2026/event/singles"):
    with Session(db) as s:
        return read.pools(s, slug)


def pool_of(found):
    names = {g["id"]: g["name"] for g in found["groups"]}
    return {s["tag"]: (s["seed"], names.get(s["group"]), s["pool_seed"]) for s in found["seeds"]}


def test_sync_copies_phases_pools_and_seeds(db):
    run, _ = sync(db, FakeStartGG())
    assert (run.counts["phases_created"], run.counts["pools_created"]) == (2, 3)
    assert run.counts["seeds_created"] == 5
    local = local_pools(db)
    found = local["found"]
    assert found["phase"] == "Pools" and local["synced_at"]
    assert [g["name"] for g in found["groups"]] == ["A1", "A2"]
    assert pool_of(found) == {"Ace": (1, "A1", 1), "KZN | Bee": (2, "A2", 1), "Cid": (3, "A2", 2)}
    assert {s["player_id"] for s in found["seeds"]} == {"1", "2", "3"}
    with Session(db) as s:
        from app.sync.models import StartggSeed

        assert s.get(StartggSeed, "7001").entrant_id == "1"  # linked to the registration
        assert s.get(StartggSeed, "7101").origin_group_id == "801"
    # Never synced: the caller asks start.gg.
    assert local_pools(db, "tournament/other/event/singles") is None


def test_new_seeding_and_pool_moves_update_the_same_seeds(db):
    fake = FakeStartGG()
    sync(db, fake)
    # Organizers reseed: Cid becomes seed 2 in A1's place... and Bee leaves the event.
    fake.seeds["700"] = [
        seed(7001, 1, 801, 1, entrant_id=1, player=1, tag="Ace"),
        seed(7003, 2, 801, 2, entrant_id=3, player=3, tag="Cid"),
    ]
    run, _ = sync(db, fake)
    assert run.counts["seeds_updated"] == 1 and run.counts["seeds_retired"] == 1
    assert pool_of(local_pools(db)["found"]) == {"Ace": (1, "A1", 1), "Cid": (2, "A1", 2)}


def test_rebuilt_pools_retire_the_old_ones(db):
    fake = FakeStartGG()
    sync(db, fake)
    fake.phases["500"][0] = phase(700, "Pools", 1, {811: "B1"}, seeds=3)
    fake.seeds["700"] = [
        seed(7001, 1, 811, 1, entrant_id=1, player=1, tag="Ace"),
        seed(7002, 2, 811, 2, entrant_id=2, player=2, tag="KZN | Bee"),
        seed(7003, 3, 811, 3, entrant_id=3, player=3, tag="Cid"),
    ]
    run, _ = sync(db, fake)
    assert run.counts["pools_retired"] == 2
    found = local_pools(db)["found"]
    assert [g["name"] for g in found["groups"]] == ["B1"]
    assert {v[1] for v in pool_of(found).values()} == {"B1"}


def test_an_empty_seed_answer_keeps_the_pools(db):
    fake = FakeStartGG()
    sync(db, fake)
    fake.seeds["700"] = []
    run, _ = sync(db, fake)
    assert "empty_seeds_kept:700" in run.warnings
    assert len(local_pools(db)["found"]["seeds"]) == 3


def test_no_phases_yet_is_a_synced_answer(db):
    fake = FakeStartGG()
    fake.phases["500"] = []
    fake.seeds = {}
    sync(db, fake)
    assert local_pools(db) == {"found": None, "synced_at": local_pools(db)["synced_at"]}


def published_seeding(db):
    """A published hub seeding of the synced event (players 1 to 5)."""
    from test_seeding import ENTRANTS, EVENT, START, dataset

    from app.seeding import service as seeding
    from app.seeding.models import SeedingProject

    with Session(db) as s:
        p = SeedingProject(
            slug="cs",
            name="Center Stage",
            startgg_event_id="500",
            startgg_event_slug="tournament/center-stage-2026/event/singles",
            startgg_videogame_id="1386",
            event_date=EVENT,
            window_start=START,
            merges={},
            duplicates={},
            published=True,
        )
        s.add(p)
        s.flush()
        rows = [
            dict(
                startgg_entrant_id=f"x{e['player_id']}",
                startgg_player_id=e["player_id"],
                gamer_tag=e["gamer_tag"],
            )
            for e in ENTRANTS
        ]
        seeding.replace_dataset(s, p, rows, dataset(), cutoff=EVENT - timedelta(days=5))
        s.flush()
        seeding.recalculate(s, p, "test")
        s.commit()


def test_public_pools_read_the_local_copy_when_startgg_is_down(db, monkeypatch):
    from app.seeding import pools

    sync(db, FakeStartGG())
    published_seeding(db)

    def down(*args, **kwargs):
        raise AssertionError("synced pools must not ask start.gg")

    monkeypatch.setattr(pools, "read_public", down)
    with client_for(db) as client:
        body = client.get("/api/v1/insights/upcoming/center-stage-2026/pools").json()
    assert body["phase"] == "Pools"
    assert [p["name"] for p in body["pools"]] == ["Pool A1", "Pool A2"]
    # The hub's seeds 1, 2 and 3 go where start.gg puts those seed numbers.
    assert [[p["seed"] for p in pool["players"]] for pool in body["pools"]] == [[1], [2, 3]]


# ------------------------------------------------------------------ sets and brackets


def local_structure(db, event_id="500"):
    with Session(db) as s:
        return read.structure(s, event_id)


def test_sync_copies_every_pools_sets_and_rebuilds_the_bracket_structure(db):
    run, _ = sync(db, FakeStartGG())
    assert run.counts["sets_created"] == 2
    local = local_structure(db)
    assert local["synced_at"]
    found = local["structure"]
    assert [g["name"] for g in found["groups"]] == ["Pools · A1", "Pools · A2"]
    a2 = found["groups"][1]["sets"][0]
    assert [s["seed"]["seedNum"] for s in a2["slots"]] == [2, 3]
    top = found["phases"][0]
    assert top["name"] == "Top 2" and [g["name"] for g in top["groups"]] == ["Top 2"]
    assert top["sources"] == {
        "7101": {"group": "801", "placement": 1, "num": 1},
        "7102": {"group": "802", "placement": 1, "num": 2},
    }
    # The pools map now knows the first-round pairs (organizers' rematch warnings).
    assert local_pools(db)["found"]["pairs"] == [[2, 3]]
    assert local_structure(db, "501") is None  # doubles: not copied, start.gg would answer


def test_results_update_sets_and_rebuilt_brackets_retire_old_ones(db):
    fake = FakeStartGG()
    sync(db, fake)
    fake.sets["802"] = [
        a_set("preview_802_1_0", 1, (7002, 2), (7003, 3), state=3, winner=2, scores=[2, 1])
    ]
    fake.sets["803"] = [a_set("9001", 1, (7101, 1), (7102, 2))]  # bracket started: real IDs
    run, _ = sync(db, fake)
    assert (run.counts["sets_updated"], run.counts["sets_created"]) == (1, 1)
    assert run.counts["sets_retired"] == 1
    with Session(db) as s:
        from app.sync.models import StartggSet

        played = s.get(StartggSet, "preview_802_1_0")
        assert (played.state, played.winner_entrant_id) == (3, "2")
        assert [slot["score"] for slot in played.slots] == [2, 1]
        assert s.get(StartggSet, "preview_803_1_0").active is False
    final = local_structure(db)["structure"]["phases"][0]["groups"][0]["sets"]
    assert [x["id"] for x in final] == ["9001"]


def test_projected_bracket_reads_the_local_copy_when_startgg_is_down(db, monkeypatch):
    from app.brackets import service as brackets

    sync(db, FakeStartGG())
    published_seeding(db)

    def down(*args, **kwargs):
        raise AssertionError("a synced bracket must not ask start.gg")

    monkeypatch.setattr(brackets, "structure", down)
    with client_for(db) as client:
        body = client.get("/api/v1/insights/upcoming/center-stage-2026").json()
    bracket = body["bracket"]
    assert bracket["source"] == "startgg" and bracket["projected"] is True
    assert [g["name"] for g in bracket["groups"]] == ["Pools · A2"]
    # The hub's seeds 2 and 3 meet where start.gg put seed numbers 2 and 3.
    match = bracket["groups"][0]["winners"][0]["sets"][0]
    assert [side["seed"] for side in match["sides"]] == [2, 3]


# ------------------------------------------------------------------ confirmed start (SH-FIX-01)

# Center Stage 2026: start.gg says Saturday 14/11 19:00 UTC (16:00 in Asunción) and keeps
# the tournament ACTIVE since Thursday; it really starts at 14:00 in Asunción = 17:00 UTC.
STARTGG_START = datetime(2026, 11, 14, 19, 0, tzinfo=UTC)
REAL_START = datetime(2026, 11, 14, 17, 0, tzinfo=UTC)


def center_stage(confirmed=True):
    return SimpleNamespace(
        start_at=STARTGG_START,
        end_at=datetime(2026, 11, 15, 23, 0, tzinfo=UTC),
        state=2,
        failures=0,
        start_confirmed_at=REAL_START if confirmed else None,
    )


def test_asuncion_times_convert_with_the_iana_zone():
    from app.core.times import from_asuncion, to_asuncion

    assert from_asuncion("2026-11-14T14:00") == REAL_START
    assert to_asuncion(REAL_START) == "2026-11-14T14:00"
    assert to_asuncion(STARTGG_START) == "2026-11-14T16:00"
    for bad in ("2026-11-14 14:00", "2026-11-14T14:00Z", "2026-13-01T10:00", ""):
        with pytest.raises(ValueError):
            from_asuncion(bad)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 11, 12, 14, 0, tzinfo=UTC), "week"),  # Thursday: ACTIVE, not live
        (datetime(2026, 11, 13, 16, 59, tzinfo=UTC), "week"),
        (datetime(2026, 11, 13, 17, 0, tzinfo=UTC), "day"),  # last 24 h before 14:00
        (datetime(2026, 11, 14, 16, 59, tzinfo=UTC), "day"),
        (datetime(2026, 11, 14, 17, 0, tzinfo=UTC), "live"),  # 14:00 in Asunción
        (datetime(2026, 11, 15, 22, 0, tzinfo=UTC), "live"),  # Sunday, before the end
        (datetime(2026, 11, 16, 5, 1, tzinfo=UTC), "finished"),
    ],
)
def test_center_stage_follows_its_confirmed_start(now, expected):
    assert service.tier(center_stage(), now) == expected


def test_frequencies_change_at_the_last_day_and_at_the_real_start():
    conf = settings()
    row = center_stage()
    for now, seconds in (
        (datetime(2026, 11, 13, 16, 0, tzinfo=UTC), 1800),
        (datetime(2026, 11, 13, 17, 0, tzinfo=UTC), 600),
        (datetime(2026, 11, 14, 17, 0, tzinfo=UTC), 180),
    ):
        assert service.next_sync(row, now, conf, failed=False) == now + timedelta(seconds=seconds)


def test_unconfirmed_tournaments_keep_their_previous_schedule():
    row = center_stage(confirmed=False)
    # Without a confirmed start: start.gg's 19:00 minus the two-hour margin, as before.
    assert service.tier(row, datetime(2026, 11, 14, 16, 59, tzinfo=UTC)) == "day"
    assert service.tier(row, datetime(2026, 11, 14, 17, 0, tzinfo=UTC)) == "live"
    assert service.tier(row, datetime(2026, 11, 13, 18, 59, tzinfo=UTC)) == "week"


def test_administrators_confirm_the_start_and_syncs_never_overwrite_it(db):
    fake = FakeStartGG()
    sync(db, fake)
    url = "/api/v1/sync/tournaments/center-stage-2026/start"
    with client_for(db) as client:
        assert client.put(url, json={"starts_at": "2026-11-14T14:00"}).status_code == 401
        bad = client.put(url, json={"starts_at": "2026-11-14T14:00Z"}, headers=AUTH)
        assert bad.status_code == 422
        r = client.put(url, json={"starts_at": "2026-11-14T14:00"}, headers=AUTH)
        assert r.status_code == 200 and r.json()["starts_at"] == "2026-11-14T14:00"
        again = client.put(url, json={"starts_at": "2026-11-14T14:00"}, headers=AUTH)
        assert again.json() == r.json()  # idempotent
        missing = "/api/v1/sync/tournaments/nope/start"
        assert client.put(missing, json={"starts_at": None}, headers=AUTH).status_code == 404
    sync(db, fake)  # start.gg still sends its own start time
    with Session(db) as s:
        row = s.get(StartggTournament, "900")
        assert row.start_confirmed_at == REAL_START and row.start_confirmed_by == "clave:Org"
        assert row.start_at == datetime.fromtimestamp(START, UTC)  # start.gg's, as received
        local = read.upcoming(s, "center-stage-2026")
        assert local["tournament"]["startAt"] == int(REAL_START.timestamp())
        assert local["tournament"]["startAtConfirmed"] is True
    with client_for(db) as client:
        status = client.get("/api/v1/sync", headers=AUTH).json()["tournaments"][0]
        assert status["start_confirmed"] is True and status["startgg_state"] == 1
        assert status["starts_at"].startswith("2026-11-14T17:00")
        cleared = client.put(url, json={}, headers=AUTH)
        assert cleared.json()["confirmed"] is False
