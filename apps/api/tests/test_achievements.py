"""Achievements (SH-ACH-01): catalog, rules, reconciliation, collections, manual grants,
showcase and the HTTP contract. No start.gg calls; the database is the disposable one."""

from datetime import UTC, datetime, timedelta

import pytest
from accounts import LEGACY_EXPIRES, WEB, make_user, sign_in
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.achievements import catalog, rules, runner, service
from app.core.config import Settings
from app.insights.engine import Data, Match
from app.main import create_app

START = datetime(2026, 3, 7, 20, tzinfo=UTC)
KEY = "k" * 32

# The 25 achievements that existed before SH-ACH-01: identifiers and names never change.
LEGACY = {
    "oracle": "Oráculo",
    "sharp_eye": "Ojo clínico",
    "against_the_tide": "Contra la corriente",
    "upset_prophet": "Profeta del batacazo",
    "top8_seer": "Vidente del Top 8",
    "full_house": "Pleno",
    "self_belief": "Fe en sí mismo",
    "self_fulfilling": "Profecía autocumplida",
    "prode_champion": "Campeón del Prode",
    "prode_podium": "Podio del Prode",
    "regular": "Habitué del Prode",
    "dynasty": "Dinastía",
    "lider": "Líder indiscutible",
    "trofeos": "Coleccionista de trofeos",
    "campeon": "Campeón",
    "amateur": "Campeón amateur",
    "david": "David contra Goliat",
    "remontadas": "Maestro de las remontadas",
    "racha": "Racha imparable",
    "top8": "Siempre en el top 8",
    "incansable": "Incansable",
    "especialista": "Especialista",
    "camaleon": "Camaleón",
    "mes": "Jugador del mes",
    "nuevo": "Nuevo en la escena",
}


# ---------------------------------------------------------------- catalog


def test_catalog_keeps_the_25_existing_and_registers_109():
    assert len(catalog.ACHIEVEMENTS) == 109
    assert len(catalog.BY_ID) == 109  # unique identifiers
    assert {a.id: a.name for a in catalog.ACHIEVEMENTS if a.legacy} == LEGACY
    assert all(len(a.id) <= 40 for a in catalog.ACHIEVEMENTS)
    states = {a.id for a in catalog.ACHIEVEMENTS if a.kind == "state"}
    assert states == {"lider", "nuevo", "especialista", "camaleon"}
    for a in catalog.ACHIEVEMENTS:
        assert a.category in catalog.CATEGORIES and a.rarity in catalog.RARITIES
        assert a.universe in catalog.UNIVERSES
        assert (a.status == "pending") == (a.pending is not None), a.id
    # Nothing that needs data we do not have is active.
    for aid in ("vbash_rojo", "bvash", "nde_ru", "dueno_del_pool", "fiel_al_regimen"):
        assert catalog.get(aid).status == "pending"


# ---------------------------------------------------------------- pure rules


def m(n, winner, loser, *, ws=None, ls=None, event="e1", days=0, hour=None):
    at = START + timedelta(days=days, minutes=10 * n)
    if hour is not None:
        at = at.replace(hour=hour)
    return Match(
        id=f"s{event}{n}",
        at=at,
        tournament_id=f"t-{event}",
        tournament=f"Open {event}",
        event_id=event,
        round=None,
        winner=winner,
        loser=loser,
        winner_seed=ws,
        loser_seed=ls,
        comeback=False,
    )


def fin(player, placement, seed, *, event="e1", entrants=16, days=0, main=True):
    return dict(
        player=player,
        placement=placement,
        seed=seed,
        entrants=entrants,
        tournament_id=f"t-{event}",
        tournament=f"Open {event}",
        event_id=event,
        event="Singles",
        city=None,
        main=main,
        starts_at=START + timedelta(days=days),
    )


def evaluate(matches, finishes, sets=None, subjects=None):
    tags = {p: p.upper() for x in matches for p in (x.winner, x.loser)}
    ctx = rules.Context(
        data=Data(matches=matches, finishes=finishes, tags=tags),
        sets=sets or {},
        subjects=subjects or {},
    )
    return rules.evaluate(ctx)


def info(rnd, ws, ls, best_of=5):
    return rules.SetInfo(round=rnd, best_of=best_of, winner_score=ws, loser_score=ls)


def bracket_through_losers():
    """A (seed 9) loses to B (seed 1) in winners, runs losers and beats B twice in the
    grand final. B is Spike in the collection tests."""
    matches = [
        m(1, "b", "a", ws=1, ls=9),
        m(2, "a", "d", ws=9, ls=3),
        m(3, "b", "c", ws=1, ls=2),
        m(4, "a", "c", ws=9, ls=2),
        m(5, "a", "b", ws=9, ls=1),
        m(6, "a", "b", ws=9, ls=1),
    ]
    sets = {
        "se11": info(1, 2, 1, 3),
        "se12": info(-1, 2, 0, 3),
        "se13": info(2, 2, 0, 3),
        "se14": info(-2, 2, 1, 3),
        "se15": info(3, 3, 1),
        "se16": info(3, 3, 0),
    }
    finishes = [fin("a", 1, 9), fin("b", 2, 1), fin("c", 3, 2), fin("d", 5, 3)]
    return matches, finishes, sets


def test_back_door_needs_the_real_path_through_losers():
    matches, finishes, sets = bracket_through_losers()
    got = evaluate(matches, finishes, sets)
    assert ("a", "puerta_de_atras") in got
    assert got[("a", "puerta_de_atras")].evidence["losers_final"] == "se14"
    assert ("a", "purete") in got  # last set 3-0
    assert ("a", "runback") in got and ("a", "ndeee") in got and ("a", "py_aguasu") in got
    # Both tiers stay: «Campeón» and the bracket ones.
    assert ("a", "campeon") in got and ("a", "mbarete") not in got
    # Without rounds the path is unknown: nothing is invented.
    unknown = {k: info(None, v.winner_score, v.loser_score) for k, v in sets.items()}
    assert ("a", "puerta_de_atras") not in evaluate(matches, finishes, unknown)


def test_champion_from_winners_is_not_back_door_but_can_reset():
    matches = [
        m(1, "a", "c", ws=1, ls=3),
        m(2, "a", "b", ws=1, ls=2),  # winners final
        m(3, "b", "c", ws=2, ls=3),  # losers final
        m(4, "b", "a", ws=2, ls=1),  # grand final: A loses the first set
        m(5, "a", "b", ws=1, ls=2),  # and wins the reset
    ]
    sets = {
        "se11": info(1, 2, 0, 3),
        "se12": info(2, 2, 1, 3),
        "se13": info(-3, 2, 1, 3),
        "se14": info(3, 3, 2),
        "se15": info(3, 3, 2),
    }
    finishes = [fin("a", 1, 1), fin("b", 2, 2), fin("c", 3, 3)]
    got = evaluate(matches, finishes, sets)
    assert ("a", "reset_y_corona") in got
    assert ("a", "puerta_de_atras") not in got
    # B lost the decisive grand final (the reset) 2-3: «Casi, kp».
    assert ("b", "casi_kp") in got
    assert got[("b", "casi_kp")].set_id == "se15"


def test_casi_kp_needs_the_decisive_final_by_one_game():
    matches = [m(1, "a", "b", ws=1, ls=2)]
    finishes = [fin("a", 1, 1), fin("b", 2, 2)]
    assert ("b", "casi_kp") not in evaluate(matches, finishes, {"se11": info(3, 3, 0)})
    assert ("b", "casi_kp") not in evaluate(matches, finishes, {"se11": info(-3, 3, 2)})
    assert ("b", "casi_kp") in evaluate(matches, finishes, {"se11": info(3, 3, 2)})


def test_spike_collection_needs_an_active_subject_and_a_real_elimination():
    matches, finishes, sets = bracket_through_losers()
    assert not any(
        k[1] in {"dictador_caido", "golpe_de_estado"} for k in evaluate(*bracket_through_losers())
    )
    got = evaluate(matches, finishes, sets, subjects={"spike": "b"})
    assert ("a", "dictador_caido") in got
    assert got[("a", "dictador_caido")].set_id == "se15"  # first win against him
    # Only the set after which Spike played no more eliminated him.
    assert got[("a", "golpe_de_estado")].set_id == "se16"
    assert ("a", "indulto") in got
    # Winning against Spike while holding the better seed is not «El Dictador ha Caído».
    better = [m(1, "x", "b", ws=1, ls=2)]
    assert ("x", "dictador_caido") not in evaluate(
        better, [fin("x", 1, 1), fin("b", 2, 2)], subjects={"spike": "b"}
    )
    # Unreliable seeding drops seeds: no seed comparison, no award.
    blind = [m(1, "x", "b")]
    assert ("x", "dictador_caido") not in evaluate(blind, [], subjects={"spike": "b"})


def test_lower_tiers_are_kept_when_a_higher_one_is_reached():
    matches = [m(i, "a", "z", ws=1, ls=2, event=f"e{i}", days=i) for i in range(1, 4)]
    finishes = [fin("a", 1, 1, event=f"e{i}", days=i, entrants=8) for i in range(1, 4)]
    got = evaluate(matches, finishes)
    assert ("a", "campeon") in got and ("a", "trofeos") in got


def test_pending_achievements_are_never_awarded():
    matches, finishes, sets = bracket_through_losers()
    got = evaluate(matches, finishes, sets, subjects={"spike": "b", "vbash": "c"})
    for _, aid in got:
        assert catalog.get(aid).status == "active", aid


# ---------------------------------------------------------------- database


def settings(**extra):
    return Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        admin_token_expires=LEGACY_EXPIRES,
        **extra,
    )


def build_scene(engine, *, published=True):
    """The bracket of bracket_through_losers() as real imported rows."""
    from app.communities.service import bootstrap
    from app.competitions.models import (
        EntrantMember,
        Event,
        EventEntrant,
        Set,
        SetSide,
        Tournament,
        TournamentParticipant,
    )
    from app.players.models import ExternalIdentity, Player

    with Session(engine) as s, s.begin():
        ids = bootstrap(s)
        tournament = Tournament(
            community_id=ids["community"],
            slug="open-marzo",
            name="Open de marzo",
            published=published,
            starts_at=START,
        )
        s.add(tournament)
        s.flush()
        event = Event(
            tournament_id=tournament.id,
            game_id=ids["game"],
            slug="singles",
            name="Ultimate Singles",
            num_entrants=16,
            main=True,
        )
        s.add(event)
        s.flush()
        people, entrants = {}, {}
        for key, seed, place, startgg in (
            ("a", 9, 1, "101"),
            ("b", 1, 2, "102"),
            ("c", 2, 3, "103"),
            ("d", 3, 5, "104"),
        ):
            player = Player(tag=key.upper() + "-tag")
            s.add(player)
            s.flush()
            s.add(
                ExternalIdentity(
                    player_id=player.id,
                    data_source_id=ids["source"],
                    external_id=f"player:{startgg}",
                    synced_at=START,
                )
            )
            participant = TournamentParticipant(
                tournament_id=tournament.id, player_id=player.id, tag_snapshot=player.tag
            )
            entrant = EventEntrant(
                event_id=event.id,
                tournament_id=tournament.id,
                name=player.tag,
                seed=seed,
                placement=place,
            )
            s.add_all([participant, entrant])
            s.flush()
            s.add(
                EntrantMember(
                    entrant_id=entrant.id,
                    event_id=event.id,
                    tournament_id=tournament.id,
                    participant_id=participant.id,
                    position=1,
                )
            )
            people[key], entrants[key] = player.id, entrant.id
        plan = [
            ("b", "a", 1, 2, 1, 3),
            ("a", "d", -1, 2, 0, 3),
            ("b", "c", 2, 2, 0, 3),
            ("a", "c", -2, 2, 1, 3),
            ("a", "b", 3, 3, 1, 5),
            ("a", "b", 3, 3, 0, 5),
        ]
        for n, (w, lo, rnd, ws, ls, bo) in enumerate(plan, 1):
            row = Set(
                event_id=event.id,
                status="completed",
                lifecycle_status="completed",
                resolution="played",
                stats_eligible=True,
                best_of=bo,
                round_number=rnd,
                round_label=f"Ronda {rnd}",
                completed_at=START + timedelta(minutes=10 * n),
            )
            s.add(row)
            s.flush()
            for side, (who, score, won) in enumerate(((w, ws, True), (lo, ls, False)), 1):
                s.add(
                    SetSide(
                        set_id=row.id,
                        event_id=event.id,
                        entrant_id=entrants[who],
                        side=side,
                        score=score,
                        is_winner=won,
                    )
                )
        return people, tournament.id


def awards(engine, player=None):
    from app.achievements.models import PlayerAchievement

    with Session(engine) as s:
        query = select(PlayerAchievement)
        if player:
            query = query.where(PlayerAchievement.player_id == player)
        return {r.achievement_id: r for r in s.scalars(query)}


def test_evaluation_is_idempotent_and_revokes_and_restores(db):
    from app.achievements.models import AchievementRun, PlayerAchievement
    from app.competitions.models import Tournament

    people, tournament_id = build_scene(db)
    first = service.run(db, trigger="test", actor="tester")
    assert first["status"] == "completed", first
    a = awards(db, people["a"])
    assert {"puerta_de_atras", "campeon", "ndeee", "purete", "bautismo"} <= set(a)
    assert "dictador_caido" not in a  # Spike's collection is off
    assert a["puerta_de_atras"].backfilled is True  # the first run is the backfill
    assert a["puerta_de_atras"].event_at == START + timedelta(minutes=60)
    recognized = {k: r.recognized_at for k, r in a.items()}
    with Session(db) as s:
        total = s.scalar(select(func.count()).select_from(PlayerAchievement))

    # A second run with the same data changes nothing: no duplicates, same dates.
    second = service.run(db, trigger="test", actor="tester")
    assert second["counts"]["added"] == 0 and second["counts"]["revoked"] == 0
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(PlayerAchievement)) == total
    assert {k: r.recognized_at for k, r in awards(db, people["a"]).items()} == recognized

    # The tournament is unpublished: its achievements are revoked, never deleted.
    with Session(db) as s, s.begin():
        s.get(Tournament, tournament_id).published = False
    service.run(db, trigger="test", actor="tester")
    a = awards(db, people["a"])
    assert a["puerta_de_atras"].status == "revoked" and a["puerta_de_atras"].revoked_at
    # Published again: reactivated with its first recognition.
    with Session(db) as s, s.begin():
        s.get(Tournament, tournament_id).published = True
    third = service.run(db, trigger="test", actor="tester")
    assert third["counts"]["restored"] > 0
    a = awards(db, people["a"])
    assert a["puerta_de_atras"].status == "active"
    assert a["puerta_de_atras"].recognized_at == recognized["puerta_de_atras"]
    assert a["puerta_de_atras"].backfilled is True
    with Session(db) as s:
        assert s.scalar(select(func.count()).select_from(AchievementRun)) == 4
        assert s.scalar(select(func.count()).select_from(PlayerAchievement)) == total


@pytest.fixture
def client(db):
    opened = []

    def make():
        c = TestClient(create_app(settings(), engine=db))
        c.__enter__()
        opened.append(c)
        return c

    yield make
    for c in opened:
        c.__exit__(None, None, None)


def test_collections_manual_grants_showcase_and_http(db, client, monkeypatch):
    people, _ = build_scene(db)
    # The admin's recalculation runs inline in tests.
    monkeypatch.setattr(
        runner,
        "start",
        lambda engine, trigger, actor: bool(service.run(engine, trigger=trigger, actor=actor)),
    )
    make_user(db, "org", role="admin")
    make_user(db, "boss", role="superadmin")
    make_user(db, "ana")
    anon = client()
    org = sign_in(client(), "org")
    boss = sign_in(client(), "boss")
    ana = sign_in(client(), "ana")

    assert anon.post("/api/v1/achievements/admin/recalculate").status_code == 401
    assert ana.post("/api/v1/achievements/admin/recalculate", headers=WEB).status_code == 403
    assert org.post("/api/v1/achievements/admin/recalculate", headers=WEB).status_code == 202

    catalog_view = anon.get("/api/v1/achievements/catalog").json()
    by_id = {a["id"]: a for a in catalog_view["achievements"]}
    assert len(by_id) == 109
    assert by_id["oracle"]["name"] == "Oráculo" and by_id["oracle"]["legacy"] is True
    assert by_id["indulto"]["name"] == "???"  # secret for whoever does not have it
    assert by_id["dictador_caido"]["available"] is False  # collection not active
    assert by_id["vbash_rojo"]["stats"]["label"] == "Pendiente"
    # 4 players: every percentage is hidden behind «Muestra chica».
    assert by_id["bautismo"]["stats"]["holders"] == 4
    assert by_id["bautismo"]["stats"]["percent"] is None
    assert by_id["bautismo"]["stats"]["label"] == "Muestra chica"
    assert by_id["mbarete"]["stats"]["label"] == "Nadie todavía"
    assert catalog_view["collections"]["spike"]["active"] is False

    # Spike by start.gg id: only a superadmin, never without consent.
    url = "/api/v1/achievements/admin/subjects/spike"
    body = dict(startgg_player_id="102", consent=False, active=True)
    assert org.put(url, json=body, headers=WEB).status_code == 403
    assert boss.put(url, json=body, headers=WEB).status_code == 422
    assert boss.put(url, json=dict(body, startgg_player_id="999"), headers=WEB).status_code == 422
    done = boss.put(url, json=dict(body, consent=True), headers=WEB)
    assert done.status_code == 200, done.text
    assert done.json()["subjects"][0]["tag"] == "B-tag"
    org.post("/api/v1/achievements/admin/recalculate", headers=WEB)
    a = awards(db, people["a"])
    assert {"dictador_caido", "golpe_de_estado", "indulto"} <= set(a)
    assert "dictador_caido" not in awards(db, people["b"])

    # Manual grants: reason required, audited, revocable.
    grant = dict(
        player_id=str(people["c"]), achievement_id="decreto_supremo", reason="Organizó Center Stage"
    )
    assert (
        org.post(
            "/api/v1/achievements/admin/grants",
            json=dict(grant, achievement_id="mbarete"),
            headers=WEB,
        ).status_code
        == 422
    )
    made = org.post("/api/v1/achievements/admin/grants", json=grant, headers=WEB)
    assert made.status_code == 201, made.text
    assert org.post("/api/v1/achievements/admin/grants", json=grant, headers=WEB).status_code == 409
    revoked = org.post(
        f"/api/v1/achievements/admin/grants/{made.json()['id']}/revoke",
        json=dict(reason="Otorgado por error"),
        headers=WEB,
    )
    assert revoked.status_code == 200
    assert awards(db, people["c"])["decreto_supremo"].status == "revoked"
    # Recalculating does not touch manual achievements.
    org.post("/api/v1/achievements/admin/recalculate", headers=WEB)
    assert awards(db, people["c"])["decreto_supremo"].status == "revoked"
    status = org.get("/api/v1/achievements/admin/status").json()
    assert status["runs"][0]["status"] == "completed" and status["catalog"]["total"] == 109

    # Ana is linked to player A: her showcase, her visibility.
    with Session(db) as s:
        from app.auth.models import User

        ana_id = s.scalar(select(User.id).where(User.username == "ana"))
    linked = boss.post(
        "/api/v1/admin/links",
        json=dict(user_id=str(ana_id), player_id=str(people["a"]), verification="En persona"),
        headers=WEB,
    )
    assert linked.status_code == 201, linked.text
    service.run(db, trigger="test", actor="tester")
    assert "ese_soy_yo" in awards(db, people["a"])
    mine = ana.get("/api/v1/achievements/me").json()
    assert mine["player_id"] == str(people["a"])
    show = "/api/v1/achievements/me/showcase"
    items = [
        dict(source="player", achievement_id="golpe_de_estado"),
        dict(source="player", achievement_id="puerta_de_atras"),
        dict(source="player", achievement_id="ndeee"),
    ]
    assert ana.put(show, json=dict(items=items)).status_code == 403  # web header
    assert ana.put(show, json=dict(items=items + items[:1]), headers=WEB).status_code == 422
    not_mine = [dict(source="player", achievement_id="mbarete")]
    assert ana.put(show, json=dict(items=not_mine), headers=WEB).status_code == 422
    assert ana.put(show, json=dict(items=items), headers=WEB).status_code == 200
    profile = anon.get(f"/api/v1/achievements/players/{people['a']}").json()
    assert profile["showcase"]["automatic"] is False
    assert [i["achievement_id"] for i in profile["showcase"]["items"]] == [
        "golpe_de_estado",
        "puerta_de_atras",
        "ndeee",
    ]
    assert profile["user_id"] == str(ana_id)
    # The secret «Indulto» is revealed to its owner only.
    assert anon.get("/api/v1/achievements/indulto").json()["name"] == "???"
    detail = ana.get("/api/v1/achievements/indulto").json()
    assert detail["name"] == "Indulto" and detail["my_awards"][0]["detail"]
    # Hiding one takes it off public pages, the showcase included.
    hide = dict(source="player", achievement_id="ndeee", hidden=True)
    assert ana.put("/api/v1/achievements/me/visibility", json=hide, headers=WEB).status_code == 200
    profile = anon.get(f"/api/v1/achievements/players/{people['a']}").json()
    assert "ndeee" not in {v["achievement_id"] for v in profile["achievements"]}
    assert len(profile["showcase"]["items"]) == 2
    # Player B has no account: automatic showcase with the rarest.
    other = anon.get(f"/api/v1/achievements/players/{people['b']}").json()
    assert other["showcase"]["automatic"] is True and other["user_id"] is None
    # The old badges endpoint keeps its shape.
    badges = anon.get(f"/api/v1/insights/players/{people['a']}").json()["badges"]
    assert {"id", "name", "why"} == set(badges[0])
    # Unknown ids.
    assert anon.get("/api/v1/achievements/no_existe").status_code == 404


def test_runner_coalesces_marks(monkeypatch):
    runner._take()
    runner.mark_dirty("results")
    runner.mark_dirty("ranking")
    assert runner._take() == "results"
    assert runner._take() is None


def test_evaluation_over_an_imported_startgg_tournament(db):
    """The engine over real imported rows (the start.gg fixture), twice."""
    import asyncio
    import json
    from pathlib import Path

    from app.achievements.models import PlayerAchievement
    from app.communities.service import bootstrap
    from app.competitions.models import Tournament
    from app.integrations.startgg.service import run_import

    class FixtureClient:
        async def download(self, slug):
            return json.loads((Path(__file__).parent / "fixtures" / "startgg.json").read_text())

    with Session(db) as s, s.begin():
        bootstrap(s)
    asyncio.run(run_import(db, FixtureClient(), "fixture-open"))
    with Session(db) as s, s.begin():
        for t in s.scalars(select(Tournament)):
            t.published = True
    first = service.run(db, trigger="test", actor="tester")
    assert first["status"] == "completed", first
    assert first["counts"]["added"] > 0
    with Session(db) as s:
        rows = list(s.scalars(select(PlayerAchievement)))
        assert {r.achievement_id for r in rows} >= {"bautismo"}
        assert all(catalog.get(r.achievement_id).status == "active" for r in rows)
    again = service.run(db, trigger="test", actor="tester")
    assert again["counts"]["added"] == 0 and again["counts"]["revoked"] == 0
