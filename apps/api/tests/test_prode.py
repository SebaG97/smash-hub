"""Prode (Mission SH-PRODE-01, ADR-020): sign-in, picks, locking, settling, achievements."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import service as auth
from app.core.config import Settings
from app.main import create_app
from app.prode import engine
from app.prode import router as prode_router

KEY = "k" * 32
ADMIN = {"Authorization": f"Bearer {KEY}", "X-Admin-Name": "Org"}
WEB = {"X-Requested-With": "smashhub"}


def settings(**extra):
    return Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        startgg_oauth_client_id="client",
        startgg_oauth_client_secret="secret-" * 4,
        startgg_oauth_redirect_uri="http://localhost:8000/api/v1/auth/startgg/callback",
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


def test_sign_in_state_is_signed_and_next_stays_on_site():
    s = settings()
    state, cookie = auth.new_state(s, "/previa/cs#prode")
    assert auth.check_state(s, state, cookie) == "/previa/cs#prode"
    assert auth.check_state(s, "other", cookie) is None
    assert auth.check_state(s, state, cookie.replace("/previa", "/x")) is None
    for unsafe in ["https://evil.example", "//evil.example", "/\\evil", None]:
        assert auth.safe_next(unsafe) == "/"
    url = auth.authorize_url(s, state)
    query = parse_qs(urlparse(url).query)
    assert url.startswith(auth.AUTHORIZE_URL)
    assert query["scope"] == ["user.identity"] and query["state"] == [state]
    assert query["redirect_uri"] == [s.startgg_oauth_redirect_uri]


def test_settings_require_https_redirect_in_production():
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            environment="development",
            database_url="postgresql://u:p@localhost/x",
            startgg_oauth_redirect_uri="ftp://x",
        )


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


def sign_in(client, monkeypatch, user_id, player, tag):
    c = client()
    identity = {"id": user_id, "slug": f"user/{tag}", "player": {"id": player, "gamerTag": tag}}
    monkeypatch.setattr(auth, "fetch_identity", lambda s, code: identity)
    start = c.get(
        "/api/v1/auth/startgg/login", params={"next": "/previa/cs#prode"}, follow_redirects=False
    )
    assert start.status_code == 303
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    back = c.get(
        "/api/v1/auth/startgg/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )
    assert back.headers["location"] == "http://localhost:3000/previa/cs#prode"
    assert "HttpOnly" in back.headers["set-cookie"]
    return c


def top8(*ids):
    return [str(i) for i in ids]


def test_prode_from_sign_in_to_achievements(db, world, monkeypatch, client):
    from app.auth.models import User
    from app.prode.models import ProdeAchievement, ProdePredictionHistory, ProdeScore

    anon = client()
    assert anon.get("/api/v1/auth/me").json() == {"enabled": True, "user": None}
    assert anon.get("/api/v1/prode/tournaments/cs").status_code == 404
    assert anon.post("/api/v1/prode/tournaments/cs").status_code == 401
    created = anon.post("/api/v1/prode/tournaments/cs", headers=ADMIN)
    assert created.status_code == 201
    contest = created.json()
    assert contest["status"] == "open" and len(contest["candidates"]) == 10
    assert anon.post("/api/v1/prode/tournaments/cs", headers=ADMIN).status_code == 409
    url = f"/api/v1/prode/contests/{contest['id']}/picks"
    vbash = sign_in(client, monkeypatch, "100", "7", "vBash")
    assert vbash.get("/api/v1/auth/me").json()["user"]["name"] == "vBash"
    picks = dict(champion="7", runner_up="1", top8=top8(1, 2, 3, 4, 5, 6, 7, 8))
    assert vbash.put(url, json=picks).status_code == 403  # no X-Requested-With
    assert anon.put(url, json=picks, headers=WEB).status_code == 401
    assert vbash.put(url, json=dict(picks, runner_up="7"), headers=WEB).status_code == 422
    assert vbash.put(url, json=dict(picks, champion="99"), headers=WEB).status_code == 422
    saved = vbash.put(url, json=dict(picks, runner_up="2"), headers=WEB)
    assert saved.status_code == 200 and saved.json()["mine"]["runner_up"] == "2"
    assert vbash.put(url, json=picks, headers=WEB).json()["mine"]["runner_up"] == "1"
    chag_fan = sign_in(client, monkeypatch, "200", "1", "Fan")
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
    # Closed: nothing gets in, and the ranking with everyone's picks shows.
    assert (
        anon.post(f"/api/v1/prode/contests/{contest['id']}/lock", headers=ADMIN).status_code == 200
    )
    assert vbash.put(url, json=picks, headers=WEB).status_code == 409
    ranking = anon.get("/api/v1/prode/tournaments/cs").json()["ranking"]
    assert {r["name"] for r in ranking} == {"vBash", "Fan"}
    # Settling waits for a final top 8.
    world["placements"] = {"7": 1, "1": 2}
    settle = f"/api/v1/prode/contests/{contest['id']}/settle"
    assert anon.post(settle, headers=ADMIN).status_code == 409
    world["placements"] = {"7": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 5, "6": 7, "8": 7, "9": 9}
    for _ in range(2):  # settling again rebuilds the same scores and achievements
        body = anon.post(settle, headers=ADMIN).json()
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
                .where(User.display_name == "vBash")
            )
        )
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
    overview = anon.get("/api/v1/prode").json()
    assert overview["leaderboard"][0]["name"] == "vBash"
    assert overview["leaderboard"][0]["precision"] == 100
    assert overview["contests"][0]["participants"] == 2
    profile = anon.get(f"/api/v1/prode/users/{overview['leaderboard'][0]['user_id']}").json()
    assert profile["points"] == 33 and profile["history"][0]["rank"] == 1
    # The hub player behind the account shows them on their profile.
    from app.integrations.models import DataSource
    from app.players.models import ExternalIdentity, Player

    with Session(db) as s, s.begin():
        source = DataSource(slug="startgg", name="start.gg", base_url="https://start.gg")
        player = Player(tag="vBash")
        s.add_all([source, player])
        s.flush()
        s.add(
            ExternalIdentity(
                player_id=player.id,
                data_source_id=source.id,
                external_id="player:7",
                synced_at=datetime.now(UTC),
            )
        )
        player_id = player.id
    shown = anon.get(f"/api/v1/prode/players/{player_id}/achievements").json()
    assert shown["achievements"][0]["rare"] is True
    assert {a["title"] for a in shown["achievements"]} >= {"Oráculo", "Pleno"}
    # Signing out revokes the session.
    assert vbash.post("/api/v1/auth/logout").status_code == 403
    assert vbash.post("/api/v1/auth/logout", headers=WEB).status_code == 204
    assert vbash.get("/api/v1/auth/me").json()["user"] is None


def test_contest_locks_itself_when_the_event_starts(db, world, monkeypatch, client):
    world["starts"] = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
    anon = client()
    contest = anon.post("/api/v1/prode/tournaments/cs", headers=ADMIN).json()
    assert contest["status"] == "locked"
    player = sign_in(client, monkeypatch, "300", "3", "Late")
    late = player.put(
        f"/api/v1/prode/contests/{contest['id']}/picks", json=dict(champion="3"), headers=WEB
    )
    assert late.status_code == 409
    assert anon.get("/api/v1/prode/tournaments/cs").json()["status"] == "locked"


def test_sign_in_rejects_a_forged_state(monkeypatch, client):
    c = client()
    monkeypatch.setattr(auth, "fetch_identity", lambda s, code: pytest.fail("must not call"))
    back = c.get(
        "/api/v1/auth/startgg/callback", params={"code": "x", "state": "y"}, follow_redirects=False
    )
    assert back.headers["location"] == "http://localhost:3000/prode?ingreso=estado"


def test_sign_in_is_off_without_oauth_settings(db):
    off = Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/test")
    with TestClient(create_app(off, engine=db)) as c:
        assert c.get("/api/v1/auth/startgg/login", follow_redirects=False).status_code == 503
        assert c.get("/api/v1/auth/me").json() == {"enabled": False, "user": None}


def test_secret_never_appears_in_settings_repr():
    s = settings()
    assert isinstance(s.startgg_oauth_client_secret, SecretStr)
    assert "secret-" not in repr(s)
