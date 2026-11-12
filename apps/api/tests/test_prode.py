"""Prode (Missions SH-PRODE-01 and SH-AUTH-01, ADR-020/021): picks with Smash Hub
accounts, locking, settling, achievements and links to player records."""

from datetime import UTC, datetime, timedelta

import pytest
from accounts import LEGACY_EXPIRES, WEB, make_user
from accounts import sign_in as account_sign_in
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.times import ASUNCION
from app.main import create_app
from app.prode import engine
from app.prode import router as prode_router

KEY = "k" * 32
# Organizers act through their session; the legacy key is checked once below.
ADMIN = WEB
LEGACY = {"Authorization": f"Bearer {KEY}", "X-Admin-Name": "Org"}


def settings(**extra):
    return Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        admin_token_expires=LEGACY_EXPIRES,
        **extra,
    )


# Pure parts.


def test_results_and_scores_follow_double_elimination_placements():
    placements = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 5, "g": 7, "h": 7, "i": 9}
    results = engine.results_from(placements)
    assert results["champion"] == ["a"] and results["runner_up"] == ["b"]
    assert set(results["top8"]) == set("abcdefgh")
    picks = dict(champion="a", runner_up="c", top8=list("abcdefgi"))
    assert engine.score(engine.DEFAULT_RULES, results, picks) == dict(
        points=10 + 7 * 2, exact_hits=1, hits=1 + 7, picks=2 + 8
    )
    # A question without a result (void) neither scores nor counts.
    assert engine.score(engine.DEFAULT_RULES, {}, picks)["picks"] == 0


def test_ranking_breaks_ties_and_shares_full_ties():
    early, late = datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 11, 2, tzinfo=UTC)
    rows = [
        dict(user_id="late", points=10, exact_hits=1, hits=3, last_saved_at=late),
        dict(user_id="early", points=10, exact_hits=1, hits=3, last_saved_at=early),
        dict(user_id="exact", points=10, exact_hits=2, hits=2, last_saved_at=late),
        dict(user_id="twin", points=10, exact_hits=1, hits=3, last_saved_at=late),
        dict(user_id="last", points=0, exact_hits=0, hits=0, last_saved_at=None),
    ]
    ranked = [(r["user_id"], r["rank"]) for r in engine.rank(rows)]
    assert ranked == [("exact", 1), ("early", 2), ("late", 3), ("twin", 3), ("last", 5)]


def test_achievements_reward_bold_and_perfect_calls():
    results = engine.results_from(
        {"7": 1, "1": 2, **{str(n): 3 + n for n in range(2, 8) if n != 7}}
    )
    results["top8"] = ["1", "2", "3", "4", "5", "6", "7", "8"]
    picks = {
        "self": dict(champion="7", runner_up="1", top8=results["top8"]),
        "fan": dict(champion="1"),
        "rival": dict(champion="3"),
    }
    ranked = [
        dict(user_id="self", rank=1, points=33),
        dict(user_id="rival", rank=2, points=2),
        dict(user_id="fan", rank=3, points=0),
    ]
    earned = engine.achievements(
        "Center Stage",
        results,
        picks,
        ranked,
        players={"self": "7", "rival": "3"},
        seeds={"7": 7, "1": 1, "3": 3},
        tags={"7": "vBash", "1": "Chag", "3": "Wesker"},
    )
    kinds = {user: {a["kind"] for a in items} for user, items in earned.items()}
    assert kinds["self"] == {
        "oracle",
        "upset_prophet",
        "self_fulfilling",
        "sharp_eye",
        "top8_seer",
        "full_house",
        "prode_champion",
    }
    assert kinds["rival"] == {"self_belief", "prode_podium"}
    assert "fan" not in kinds  # no hits and no points: nothing
    oracle = next(a for a in earned["self"] if a["kind"] == "oracle")
    assert oracle["detail"] == "Dijo que ganaba vBash en Center Stage."
    lifetime = engine.lifetime({"u": 3, "v": 1}, {"u": 2})
    assert {a["kind"] for a in lifetime["u"]} == {"regular", "dynasty"} and "v" not in lifetime


# With PostgreSQL.

ENTRANTS = [
    dict(startgg_player_id=str(n), startgg_entrant_id=f"e{n}", gamer_tag=f"P{n}", prefix=None)
    for n in range(1, 11)
]


@pytest.fixture
def world(db, monkeypatch):
    starts = int((datetime.now(UTC) + timedelta(days=3)).timestamp())
    state = dict(entrants=list(ENTRANTS), starts=starts, placements={})

    def upcoming(request, slug):
        tournament = dict(id=1, name="Center Stage", slug=f"tournament/{slug}", startAt=starts)
        event = dict(
            id=55,
            name="Ultimate Singles",
            slug=f"tournament/{slug}/event/singles",
            startAt=state["starts"],
        )
        return tournament, event, state["entrants"]

    import app.insights.router as insights

    monkeypatch.setattr(insights, "_upcoming", upcoming)
    monkeypatch.setattr(prode_router, "_seeds", lambda s, event: {str(n): n for n in range(1, 11)})
    monkeypatch.setattr(
        prode_router, "_final_placements", lambda request, event_id: state["placements"]
    )
    return state


@pytest.fixture
def client(db):
    """A client with the app's lifespan running (it creates the engine); closed after."""
    opened = []

    def make():
        c = TestClient(create_app(settings(), engine=db))
        c.__enter__()
        opened.append(c)
        return c

    yield make
    for c in opened:
        c.__exit__(None, None, None)


def sign_in(client, db, username, display_name=None):
    """A forecaster with their own account, signed in on a fresh client."""
    make_user(db, username)
    c = account_sign_in(client(), username)
    if display_name:
        c.put("/api/v1/auth/me", json=dict(display_name=display_name), headers=WEB)
    return c


def hub_player(db, tag, startgg_id):
    from app.integrations.models import DataSource
    from app.players.models import ExternalIdentity, Player

    with Session(db) as s, s.begin():
        source = s.scalar(select(DataSource).where(DataSource.slug == "startgg"))
        if source is None:
            source = DataSource(slug="startgg", name="start.gg", base_url="https://start.gg")
            s.add(source)
        player = Player(tag=tag)
        s.add(player)
        s.flush()
        s.add(
            ExternalIdentity(
                player_id=player.id,
                data_source_id=source.id,
                external_id=f"player:{startgg_id}",
                synced_at=datetime.now(UTC),
            )
        )
        return player.id


def top8(*ids):
    return [str(i) for i in ids]


def test_prode_from_sign_in_to_achievements(db, world, monkeypatch, client):
    from app.auth.models import User
    from app.prode.models import (
        ProdeAchievement,
        ProdeAuditEntry,
        ProdePrediction,
        ProdePredictionHistory,
        ProdeScore,
    )

    anon = client()
    me = anon.get("/api/v1/auth/me").json()
    assert me["user"] is None and me["legacy_admin_key"] is True
    assert anon.get("/api/v1/prode/tournaments/cs").status_code == 404
    assert anon.post("/api/v1/prode/tournaments/cs", headers=WEB).status_code == 401
    # A forecaster's account cannot organize.
    vbash = sign_in(client, db, "vbash", "vBash")
    assert vbash.post("/api/v1/prode/tournaments/cs", headers=WEB).status_code == 403
    # Organizers use their own session; the audit records their username.
    make_user(db, "org", role="admin")
    org = account_sign_in(client(), "org")
    assert org.post("/api/v1/prode/tournaments/cs").status_code == 403  # no web header
    created = org.post("/api/v1/prode/tournaments/cs", headers=ADMIN)
    assert created.status_code == 201
    contest = created.json()
    assert contest["status"] == "open" and len(contest["candidates"]) == 10
    assert org.post("/api/v1/prode/tournaments/cs", headers=ADMIN).status_code == 409
    url = f"/api/v1/prode/contests/{contest['id']}/picks"
    assert vbash.get("/api/v1/auth/me").json()["user"]["name"] == "vBash"
    picks = dict(champion="7", runner_up="1", top8=top8(1, 2, 3, 4, 5, 6, 7, 8))
    assert vbash.put(url, json=picks).status_code == 403  # no X-Requested-With
    assert anon.put(url, json=picks, headers=WEB).status_code == 401
    assert vbash.put(url, json=dict(picks, runner_up="7"), headers=WEB).status_code == 422
    assert vbash.put(url, json=dict(picks, champion="99"), headers=WEB).status_code == 422
    saved = vbash.put(url, json=dict(picks, runner_up="2"), headers=WEB)
    assert saved.status_code == 200 and saved.json()["mine"]["runner_up"] == "2"
    assert vbash.put(url, json=picks, headers=WEB).json()["mine"]["runner_up"] == "1"
    # Someone who is not a player plays too: an account needs no player record.
    chag_fan = sign_in(client, db, "fan", "Fan")
    chag_fan.put(
        url, json=dict(champion="1", runner_up="2", top8=top8(1, 2, 3, 4, 5, 6, 8, 9)), headers=WEB
    )
    # Others' picks stay hidden while open.
    view = chag_fan.get("/api/v1/prode/tournaments/cs").json()
    assert view["participants"] == 2 and view["ranking"] == []
    assert view["mine"]["champion"] == "1"
    # P10 leaves start.gg: kept, marked withdrawn, no longer pickable.
    world["entrants"] = ENTRANTS[:9]
    view = anon.get("/api/v1/prode/tournaments/cs").json()
    assert [c["withdrawn"] for c in view["candidates"] if c["startgg_player_id"] == "10"] == [True]
    assert chag_fan.put(url, json=dict(champion="10"), headers=WEB).status_code == 422
    # Closed with the legacy key (still valid during the transition): nothing gets in.
    lock = f"/api/v1/prode/contests/{contest['id']}/lock"
    assert anon.post(lock, headers=LEGACY).status_code == 200
    assert vbash.put(url, json=picks, headers=WEB).status_code == 409
    ranking = anon.get("/api/v1/prode/tournaments/cs").json()["ranking"]
    assert {r["name"] for r in ranking} == {"vBash", "Fan"}
    # vBash's account is linked to the hub player behind start.gg player 7.
    make_user(db, "boss", role="superadmin")
    boss = account_sign_in(client(), "boss")
    player_id = hub_player(db, "vBash", "7")
    with Session(db) as s:
        vbash_id = s.scalar(select(User.id).where(User.username == "vbash"))
    linked = boss.post(
        "/api/v1/admin/links",
        json=dict(
            user_id=str(vbash_id),
            player_id=str(player_id),
            verification="Lo confirmó en persona en Center Stage",
        ),
        headers=WEB,
    )
    assert linked.status_code == 201, linked.text
    # Settling waits for a final top 8.
    world["placements"] = {"7": 1, "1": 2}
    settle = f"/api/v1/prode/contests/{contest['id']}/settle"
    assert org.post(settle, headers=ADMIN).status_code == 409
    world["placements"] = {"7": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 5, "6": 7, "8": 7, "9": 9}
    for _ in range(2):  # settling again rebuilds the same scores and achievements
        body = org.post(settle, headers=ADMIN).json()
        assert body["status"] == "settled"
        assert [(r["name"], r["points"], r["rank"]) for r in body["ranking"]] == [
            ("vBash", 10 + 7 + 16, 1),
            ("Fan", 7 * 2, 2),
        ]
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(ProdeScore)) == 2
        kinds = set(
            s.scalars(
                select(ProdeAchievement.kind)
                .join(User, User.id == ProdeAchievement.user_id)
                .where(User.username == "vbash")
            )
        )
        # "Profecía autocumplida" needs the link: he picked his own player as champion.
        assert {
            "oracle",
            "upset_prophet",
            "self_fulfilling",
            "full_house",
            "prode_champion",
        } <= kinds
        assert s.scalar(select(func.count()).select_from(ProdeAchievement)) == len(
            set(s.execute(select(ProdeAchievement.user_id, ProdeAchievement.kind)).all())
        )
        # vBash saved three picks, then changed only the runner-up; Fan saved three.
        assert s.scalar(select(func.count()).select_from(ProdePredictionHistory)) == 3 + 1 + 3
        actors = set(s.scalars(select(ProdeAuditEntry.actor)))
        assert {"org", "clave:Org"} <= actors
    overview = anon.get("/api/v1/prode").json()
    assert overview["leaderboard"][0]["name"] == "vBash"
    assert overview["leaderboard"][0]["precision"] == 100
    assert overview["contests"][0]["participants"] == 2
    leader = overview["leaderboard"][0]["user_id"]
    profile = anon.get(f"/api/v1/prode/users/{leader}").json()
    assert profile["points"] == 33 and profile["history"][0]["rank"] == 1
    assert profile["player_id"] == str(player_id)
    # The linked player shows the achievements on their record.
    shown = anon.get(f"/api/v1/prode/players/{player_id}/achievements").json()
    assert shown["achievements"][0]["rare"] is True
    assert {a["title"] for a in shown["achievements"]} >= {"Oráculo", "Pleno"}
    # Unlinking hides them from the player record but keeps everything on the account.
    with Session(db) as s:
        before = (
            s.scalar(select(func.count()).select_from(ProdePrediction)),
            s.scalar(select(func.count()).select_from(ProdeAchievement)),
        )
    link_id = boss.get("/api/v1/admin/links").json()[0]["id"]
    unlinked = boss.post(
        f"/api/v1/admin/links/{link_id}/unlink", json=dict(reason="Pidió desvincular"), headers=WEB
    )
    assert unlinked.status_code == 200
    assert anon.get(f"/api/v1/prode/players/{player_id}/achievements").json() == {
        "user_id": None,
        "achievements": [],
    }
    profile = anon.get(f"/api/v1/prode/users/{leader}").json()
    assert profile["player_id"] is None and profile["points"] == 33
    assert {a["title"] for a in profile["achievements"]} >= {"Oráculo", "Pleno"}
    with Session(db) as s:
        assert before == (
            s.scalar(select(func.count()).select_from(ProdePrediction)),
            s.scalar(select(func.count()).select_from(ProdeAchievement)),
        )
    # Signing out revokes the session.
    assert vbash.post("/api/v1/auth/logout").status_code == 403
    assert vbash.post("/api/v1/auth/logout", headers=WEB).status_code == 204
    assert vbash.get("/api/v1/auth/me").json()["user"] is None


def test_contest_locks_itself_when_the_event_starts(db, world, client):
    world["starts"] = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
    anon = client()
    contest = anon.post("/api/v1/prode/tournaments/cs", headers=LEGACY).json()
    assert contest["status"] == "locked"
    player = sign_in(client, db, "late")
    late = player.put(
        f"/api/v1/prode/contests/{contest['id']}/picks", json=dict(champion="3"), headers=WEB
    )
    assert late.status_code == 409
    assert anon.get("/api/v1/prode/tournaments/cs").json()["status"] == "locked"


def test_start_gg_sign_in_is_gone(db):
    with TestClient(create_app(settings(), engine=db)) as c:
        assert c.get("/api/v1/auth/startgg/login", follow_redirects=False).status_code == 404


def test_disabled_accounts_leave_the_leaderboard_but_keep_their_data(db, world, client):
    from app.prode.models import ProdePrediction

    anon = client()
    contest = anon.post("/api/v1/prode/tournaments/cs", headers=LEGACY).json()
    fan = sign_in(client, db, "fan2", "Fan")
    url = f"/api/v1/prode/contests/{contest['id']}/picks"
    assert fan.put(url, json=dict(champion="1"), headers=WEB).status_code == 200
    make_user(db, "boss2", role="superadmin")
    boss = account_sign_in(client(), "boss2")
    fan_id = fan.get("/api/v1/auth/me").json()["user"]["id"]
    off = boss.put(
        f"/api/v1/admin/users/{fan_id}/status",
        json=dict(disabled=True, reason="Cuenta duplicada"),
        headers=WEB,
    )
    assert off.status_code == 200 and off.json()["disabled"] is True
    assert fan.get("/api/v1/auth/me").json()["user"] is None  # sessions closed
    assert anon.get(f"/api/v1/prode/users/{fan_id}").status_code == 404
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(ProdePrediction)) == 1


# SH-FIX-01: organizers move the close to the real start, in Asunción time.


def test_organizers_move_the_close_keeping_every_pick(db, world, client):
    from app.prode.models import ProdeAuditEntry, ProdeContest, ProdePrediction

    anon = client()
    contest = anon.post("/api/v1/prode/tournaments/cs", headers=LEGACY).json()
    fan = sign_in(client, db, "early")
    picks = f"/api/v1/prode/contests/{contest['id']}/picks"
    assert fan.put(picks, json=dict(champion="1", top8=["1", "2"]), headers=WEB).status_code == 200
    url = f"/api/v1/prode/contests/{contest['id']}/locks-at"
    later = (datetime.now(UTC) + timedelta(days=2)).astimezone(ASUNCION)
    local = later.strftime("%Y-%m-%dT14:00")
    assert fan.post(url, json=dict(locks_at=local), headers=WEB).status_code == 403
    assert anon.post(url, json=dict(locks_at="mañana"), headers=LEGACY).status_code == 422
    moved = anon.post(url, json=dict(locks_at=local), headers=LEGACY)
    assert moved.status_code == 200
    expected = datetime.fromisoformat(local).replace(tzinfo=ASUNCION)
    assert datetime.fromisoformat(moved.json()["locks_at"]) == expected
    assert expected.astimezone(UTC).hour == 17  # 14:00 in Asunción
    assert moved.json()["participants"] == 1
    again = anon.post(url, json=dict(locks_at=local), headers=LEGACY)
    assert again.json()["locks_at"] == moved.json()["locks_at"]
    past = anon.post(url, json=dict(locks_at="2020-01-01T10:00"), headers=LEGACY)
    assert past.status_code == 422
    with Session(db) as s:
        changes = s.scalars(
            select(ProdeAuditEntry).where(ProdeAuditEntry.action == "set_locks_at")
        ).all()
        assert len(changes) == 1  # the repeated request changed nothing
        assert s.scalar(select(func.count()).select_from(ProdePrediction)) == 2
        # The close arrives: the backend refuses any change, whatever the page shows.
        row = s.get(ProdeContest, contest["id"])
        row.locks_at = datetime.now(UTC) - timedelta(seconds=1)
        s.commit()
    late = fan.put(picks, json=dict(champion="2"), headers=WEB)
    assert late.status_code == 409
    assert anon.post(url, json=dict(locks_at=local), headers=LEGACY).status_code == 409
    mine = fan.get("/api/v1/prode/tournaments/cs").json()["mine"]
    assert mine["champion"] == "1" and mine["top8"] == ["1", "2"]


def test_a_confirmed_start_sets_the_close_of_new_contests(db):
    from app.prode import service

    real = int(datetime(2026, 11, 14, 17, 0, tzinfo=UTC).timestamp())
    startgg = int(datetime(2026, 11, 14, 19, 0, tzinfo=UTC).timestamp())
    with Session(db) as s:
        contest = service.create(
            s,
            slug="cs",
            tournament=dict(name="CS", startAt=real, startAtConfirmed=True),
            event=dict(id=55, slug="tournament/cs/event/s", name="Singles", startAt=startgg),
            entrants=[],
            seeds={},
            actor="org",
        )
        assert contest.locks_at == datetime(2026, 11, 14, 17, 0, tzinfo=UTC)
        other = service.create(
            s,
            slug="ot",
            tournament=dict(name="OT", startAt=real),
            event=dict(id=56, slug="tournament/ot/event/s", name="Singles", startAt=startgg),
            entrants=[],
            seeds={},
            actor="org",
        )
        assert other.locks_at == datetime(2026, 11, 14, 19, 0, tzinfo=UTC)  # unchanged
