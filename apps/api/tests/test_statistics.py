"""PostgreSQL-only fixtures; automated statistics tests never call start.gg."""

import copy
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from test_set_classification import raw_result, unused_reset_raw
from test_startgg import prepare, run
from test_startgg import snapshot as snapshot

from app.cli import validate_statistics
from app.communities.models import Community
from app.competitions.models import Event, Set, Tournament
from app.core.config import Settings
from app.games.models import Game
from app.integrations.models import ExternalMapping
from app.integrations.startgg.classification import scoreless_statistics_evidence
from app.main import create_app
from app.players.models import ExternalIdentity, Player


@pytest.fixture
def competition(db, snapshot):
    prepare(db)
    singles = snapshot["events"][0]
    singles["sets"] += [
        raw_result(id="final"),
        unused_reset_raw(),
        raw_result(
            id="placeholder",
            state=1,
            winnerId=None,
            completedAt=None,
            slots=[{"entrant": None, "prereqType": "bye"}] * 2,
        ),
        raw_result(id="winner_missing", winnerId=None),
    ]
    doubles = raw_result(id="doubles")
    doubles["winnerId"] = 21
    doubles["slots"][0]["entrant"]["id"] = "21"
    doubles["slots"][1]["entrant"]["id"] = "22"
    snapshot["events"][1]["sets"] = [doubles]
    run(db, snapshot)
    with Session(db) as s:
        ids = dict(
            s.execute(select(ExternalIdentity.external_id, ExternalIdentity.player_id)).all()
        )
        game_id = s.scalar(select(Game.id).where(Game.slug == "super-smash-bros-ultimate"))
        tournament_id = s.scalar(select(Tournament.id))
        community_id = s.scalar(select(Community.id).where(Community.slug == "smash-paraguay"))
    with TestClient(
        create_app(
            Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/test"),
            engine=db,
        )
    ) as client:
        yield {
            "client": client,
            "a": str(ids["player:100"]),
            "b": str(ids["player:101"]),
            "c": str(ids["player:102"]),
            "game": str(game_id),
            "tournament": str(tournament_id),
            "community": str(community_id),
            "snapshot": snapshot,
            "db": db,
        }


def get(ctx, path="statistics", who="a", **params):
    return ctx["client"].get(
        f"/api/v1/players/{ctx[who]}/{path}", params={"game_id": ctx["game"], **params}
    )


def test_valid_win_loss_homonyms_and_missing_dates(competition):
    a = get(competition).json()
    b = get(competition, who="b").json()
    assert a["player"]["tag"] == b["player"]["tag"] == "Same"
    assert a["player"]["id"] != b["player"]["id"]
    assert (a["sets_played"], a["wins"], a["losses"], a["win_rate"]) == (4, 4, 0, 100)
    assert (b["sets_played"], b["wins"], b["losses"], b["win_rate"]) == (4, 0, 4, 0)
    assert a["wins"] == b["losses"]
    assert a["tournaments_played"] == a["tournaments_registered"] == 1
    assert a["unique_opponents"] == 1
    assert a["best_final_placement"] == 1
    assert a["first_set_at"] is not None and a["latest_tournament"] is not None


def test_no_sets_and_no_denominator(competition):
    result = get(competition, who="c").json()
    assert result["sets_played"] == 0 and result["wins"] == result["losses"] == 0
    for key in (
        "win_rate",
        "first_set_at",
        "last_set_at",
        "latest_tournament",
        "best_final_placement",
    ):
        assert result[key] is None
    assert get(competition, "matches", who="c").json()["items"] == []


def test_history_excludes_administrative_and_keeps_scoreless_winner(competition):
    response = get(competition, "matches")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 4
    rows = data["items"]
    assert {r["round_label"] for r in rows} == {"Final", "Missing score", "Missing date"}
    scoreless = next(r for r in rows if r["round_label"] == "Missing score")
    assert scoreless["score"] is scoreless["opponent_score"] is None
    assert scoreless["result"] == "W" and scoreless["stats_eligible"] is True
    assert all(r["opponents"][0]["id"] == competition["b"] for r in rows)
    assert all(r["source_url"] == "https://www.start.gg/tournament/fixture-open" for r in rows)
    assert rows[-1]["completed_at"] is None


@pytest.mark.parametrize("path", ["statistics", "matches", "opponents", "placements"])
def test_endpoint_contract_and_uuid_errors(competition, path):
    response = get(competition, path)
    assert response.status_code == 200, response.text
    assert response.json()["filters"]["game_id"] == competition["game"]
    assert "source_result" not in response.text and "external_id" not in response.text
    url = f"/api/v1/players/{uuid4()}/{path}"
    assert (
        competition["client"].get(url, params={"game_id": competition["game"]}).status_code == 404
    )
    assert competition["client"].get(url).status_code == 422


def test_h2h_symmetric_and_chronological(competition):
    a = get(competition, f"head-to-head/{competition['b']}").json()
    b = get(competition, f"head-to-head/{competition['a']}", who="b").json()
    assert a["encounters"] == b["encounters"] == 4
    assert a["wins_a"] == b["wins_b"] == 4
    assert a["win_rate_b"] == b["win_rate_a"] == 0
    assert [r["id"] for r in a["history"]["items"]] == [r["id"] for r in b["history"]["items"]]
    assert all(r["result"] == "L" for r in b["history"]["items"])


def test_h2h_never_played_self_and_unknown(competition):
    empty = get(competition, f"head-to-head/{competition['c']}").json()
    assert empty["encounters"] == 0 and empty["win_rate_a"] is empty["win_rate_b"] is None
    assert empty["history"]["items"] == []
    assert get(competition, f"head-to-head/{competition['a']}").status_code == 422
    assert get(competition, f"head-to-head/{uuid4()}").status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"date_from": "2023-11-14"},
        {"date_from": "2023-11-14T12:00:00"},
        {"date_from": "2024-01-02T00:00:00Z", "date_to": "2024-01-01T00:00:00Z"},
        {"date_from": "2024-01-01T00:00:00Z", "date_to": "2024-01-01T00:00:00Z"},
        {"mode": "teams"},
        {"page_size": 101},
        {"page": 0},
        {"country_id": str(uuid4())},
        {"region_id": str(uuid4())},
        {"game_id": "bad"},
    ],
)
def test_invalid_filters(competition, params):
    assert get(competition, "matches", **params).status_code == 422


def test_date_boundaries_timezone_and_unknown_dates(competition):
    start = datetime.fromtimestamp(1700000000, UTC).isoformat()
    end = datetime.fromtimestamp(1700000001, UTC).isoformat()
    # Timestamp filters never fall back to tournament start or import time.
    assert get(competition, date_from=start, date_to=end).json()["sets_played"] == 3
    assert get(competition, date_to=start).json()["sets_played"] == 0
    assert get(competition, date_from=end).json()["sets_played"] == 0
    assert (
        get(competition, date_from="2023-11-14T19:13:20-03:00", date_to=end).json()["sets_played"]
        == 3
    )


def test_tournament_game_and_community_filters(competition):
    for name in ("tournament_id", "game_id", "community_id"):
        assert get(competition, **{name: str(uuid4())}).json()["sets_played"] == 0
    assert (
        get(
            competition,
            tournament_id=competition["tournament"],
            community_id=competition["community"],
        ).json()["sets_played"]
        == 4
    )


def test_doubles_separate_rosters_and_teammates_not_opponents(competition):
    a = get(competition, mode="doubles").json()
    assert a["sets_played"] == a["wins"] == 1 and a["unique_opponents"] == 2
    assert get(competition, who="c", mode="doubles").json()["losses"] == 1
    assert (
        get(competition, f"head-to-head/{competition['b']}", mode="doubles").json()["encounters"]
        == 0
    )
    assert (
        get(competition, f"head-to-head/{competition['c']}", mode="doubles").json()["encounters"]
        == 1
    )
    assert len(get(competition, "matches", mode="doubles").json()["items"][0]["opponents"]) == 2


def test_placements_provisional_and_registration_without_activity(db, snapshot):
    prepare(db)
    snapshot["events"][0]["sets"] = []
    snapshot["events"][0]["standings"][0]["isFinal"] = False
    run(db, snapshot)
    with Session(db) as s:
        id = s.scalar(
            select(ExternalIdentity.player_id).where(ExternalIdentity.external_id == "player:100")
        )
        game = s.scalar(select(Game.id).where(Game.slug == "super-smash-bros-ultimate"))
    with TestClient(
        create_app(
            Settings(_env_file=None, database_url="postgresql://u:p@localhost/test"), engine=db
        )
    ) as c:
        url = f"/api/v1/players/{id}"
        stats = c.get(url + "/statistics", params={"game_id": str(game)}).json()
        assert stats["tournaments_registered"] == 1 and stats["tournaments_played"] == 0
        assert stats["best_final_placement"] is None
        assert c.get(url + "/placements", params={"game_id": str(game)}).json()["items"] == []


def test_pagination_stable_ties_and_opponents(competition):
    full = get(competition, "matches").json()
    pages = [
        get(competition, "matches", page=n, page_size=1).json()["items"][0]["id"]
        for n in range(1, 5)
    ]
    assert pages == [r["id"] for r in full["items"]] and len(set(pages)) == 4
    assert get(competition, "matches", page=5, page_size=1).json()["items"] == []
    rivals = get(competition, "opponents").json()
    assert rivals["total"] == 1 and rivals["items"][0]["sets_played"] == 4
    assert rivals["items"][0]["opponent"]["id"] == competition["b"]
    doubles = get(competition, "opponents", mode="doubles").json()["items"]
    assert [r["opponent"]["id"] for r in doubles] == sorted(r["opponent"]["id"] for r in doubles)
    assert get(competition, "placements", page_size=1).json()["total"] == 1


def test_reimport_correction_and_current_tag(competition):
    before = get(competition).json()
    run(competition["db"], competition["snapshot"])
    assert get(competition).json() == before
    data = copy.deepcopy(competition["snapshot"])
    result = data["events"][0]["sets"][0]
    result["winnerId"] = 12
    result["updatedAt"] += 1
    result["slots"][0]["standing"]["stats"]["score"]["value"] = 0
    result["slots"][1]["standing"]["stats"]["score"]["value"] = 2
    run(competition["db"], data)
    stats = get(competition).json()
    assert (stats["sets_played"], stats["wins"], stats["losses"], stats["win_rate"]) == (
        4,
        3,
        1,
        75,
    )
    with Session(competition["db"]) as s, s.begin():
        row = s.get(Player, competition["a"])
        row.tag = "New tag"
    assert get(competition).json()["player"]["tag"] == "New tag"
    assert (
        get(competition, who="b", path="opponents").json()["items"][0]["opponent"]["tag"]
        == "New tag"
    )


@pytest.mark.parametrize("locked", ["set", "mapping"])
def test_pending_administrative_review_excluded(competition, locked):
    with Session(competition["db"]) as s, s.begin():
        model = Set if locked == "set" else ExternalMapping
        if locked == "set":
            row = s.scalar(select(Set).where(Set.round_label == "Missing score"))
        else:
            row = s.scalar(
                select(model).where(model.external_id == "1005", model.entity_type == "set")
            )
        row.manual_locked = True
    assert get(competition).json()["sets_played"] == 3


def test_ambiguous_modality_excluded(competition):
    with Session(competition["db"]) as s, s.begin():
        row = s.scalar(select(Event).where(Event.team_size == 1))
        row.competition_type = None
    assert get(competition).json()["sets_played"] == 0


def test_no_n_plus_one(competition):
    statements = []

    def record(conn, cursor, statement, params, context, many):
        statements.append(statement)

    event.listen(competition["db"], "before_cursor_execute", record)
    try:
        assert get(competition, "matches", page_size=1).status_code == 200
        small = len(statements)
        statements.clear()
        assert get(competition, "matches", page_size=100).status_code == 200
        assert len(statements) == small <= 6
    finally:
        event.remove(competition["db"], "before_cursor_execute", record)


def extra_tournament(data, offset, other_game=False):
    data = copy.deepcopy(data)
    t = data["tournament"]
    t.update(id=100 + offset, slug=f"tournament/extra-{offset}", name=f"Extra {offset}")
    t["startAt"] += offset * 100000
    t["endAt"] += offset * 100000
    e = data["events"][0]
    data["events"] = [e]
    e["id"] += offset
    t["events"] = [{"id": e["id"]}]
    for p in data["participants"]:
        p["id"] += offset
        if p["player"] and p["player"]["id"] == 100:
            p["gamerTag"] = "New tag"
    by_id = {p["id"]: p for p in data["participants"]}
    for entrant in e["entrants"]:
        entrant["id"] += offset
        entrant["participants"] = [by_id[p["id"] + offset] for p in entrant["participants"]]
    for standing in e["standings"]:
        standing["id"] += offset
        standing["entrant"]["id"] += offset
    e["sets"] = [e["sets"][0]]
    r = e["sets"][0]
    r["id"] = str(int(r["id"]) + offset)
    r["winnerId"] = int(r["winnerId"]) + offset
    r["completedAt"] += offset * 100000
    for slot in r["slots"]:
        slot["entrant"]["id"] = int(slot["entrant"]["id"]) + offset
    if other_game:
        e["videogame"] = {"id": 9999, "name": "Another game"}
    return data


def test_shared_identity_multiple_tournaments_games_and_aliases(competition):
    second = extra_tournament(competition["snapshot"], 200)
    third = extra_tournament(competition["snapshot"], 400, other_game=True)
    run(competition["db"], second)
    run(competition["db"], third)
    result = get(competition).json()
    assert result["player"]["tag"] == "New tag"
    assert result["sets_played"] == 5 and result["tournaments_played"] == 2
    assert result["tournaments_registered"] == 2
    assert get(competition, tournament_id=competition["tournament"]).json()["sets_played"] == 4
    with Session(competition["db"]) as s:
        other = s.scalar(select(Game.id).where(Game.name == "Another game"))
    assert get(competition, game_id=str(other)).json()["sets_played"] == 1
    h = get(competition, f"head-to-head/{competition['b']}").json()
    assert h["encounters"] == 5
    assert get(competition, "placements").json()["total"] == 2
    run(competition["db"], second)
    assert get(competition).json() == result


def test_unpublished_data_hidden(competition):
    with Session(competition["db"]) as s, s.begin():
        s.scalar(select(Tournament)).published = False
    for path in ("statistics", "matches", "opponents", "placements"):
        assert get(competition, path).status_code == 404


def test_unsafe_source_slug_not_linked(competition):
    with Session(competition["db"]) as s, s.begin():
        s.scalar(select(Tournament)).slug = "https://evil.example/secret"
    assert all(row["source_url"] is None for row in get(competition, "matches").json()["items"])


@pytest.mark.parametrize(
    "kind",
    [
        "valid",
        "pending",
        "no_winner",
        "dq",
        "bye",
        "placeholder",
        "same_entrant",
        "one_entrant",
        "partial_score",
        "bad_score",
        "invalid_source",
    ],
)
def test_scoreless_exception_conservative(kind):
    source = raw_result()
    for slot in source["slots"]:
        slot["standing"] = None
    if kind == "pending":
        source["state"] = 1
    elif kind == "no_winner":
        source["winnerId"] = None
    elif kind in {"dq", "bye"}:
        source["displayScore"] = kind.upper()
    elif kind == "placeholder":
        source["hasPlaceholder"] = True
    elif kind == "same_entrant":
        source["slots"][1]["entrant"] = source["slots"][0]["entrant"]
    elif kind == "one_entrant":
        source["slots"][1]["entrant"] = None
    elif kind in {"partial_score", "bad_score"}:
        source["slots"][1]["standing"] = {
            "stats": {"score": {"value": 1 if kind == "partial_score" else -1}}
        }
    elif kind == "invalid_source":
        source = None
    assert scoreless_statistics_evidence(source) is (kind == "valid")


@pytest.mark.parametrize(
    "environment,url",
    [
        ("production", "postgresql://u:p@localhost/smashhub"),
        ("development", "postgresql://u:p@remote.example/smashhub"),
        ("development", "postgresql://u:p@localhost/other"),
    ],
)
def test_audit_refuses_production_remote_and_other_database(monkeypatch, environment, url):
    monkeypatch.setattr("sys.argv", ["validate_statistics", "--slugs", "fixture-open"])
    monkeypatch.setattr(
        validate_statistics,
        "get_settings",
        lambda: SimpleNamespace(environment=environment, database_url=SecretStr(url)),
    )

    def forbidden(settings):
        pytest.fail("Audit must reject configuration before constructing an engine")

    monkeypatch.setattr(validate_statistics, "build_engine", forbidden)
    with pytest.raises(SystemExit, match="Refusing"):
        validate_statistics.main()


def test_registration_placement_period_policy(competition):
    # Tournament starts before the dated sets. Both concepts retain their own
    # documented date policy instead of silently manufacturing activity.
    params = {"date_from": "2023-11-14T22:13:20Z", "date_to": "2023-11-14T22:13:21Z"}
    result = get(competition, **params).json()
    assert result["sets_played"] == 3
    assert result["tournaments_registered"] == 0
    assert result["best_final_placement"] is None
    assert get(competition, "placements", **params).json()["total"] == 0
    assert get(competition, "opponents", **params).json()["items"][0]["sets_played"] == 3
    assert get(competition, f"head-to-head/{competition['b']}", **params).json()["encounters"] == 3
