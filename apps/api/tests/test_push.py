"""Uploading a seeding to start.gg (Mission 30). start.gg is faked: nothing is written."""

import pytest
from pydantic import SecretStr
from test_seeding import AUTH, KEY, client_for
from test_seeding import project as project

from app.core.config import Settings
from app.main import create_app
from app.seeding import push

SEEDS = [
    dict(id="s1", seed=1, player_id="10", tag="Ace"),
    dict(id="s2", seed=2, player_id="20", tag="Bee"),
    dict(id="s3", seed=3, player_id="30", tag="Cid"),
]
ROWS = [
    dict(seed=1, player_id="20", gamer_tag="Bee"),
    dict(seed=2, player_id="10", gamer_tag="Ace"),
    dict(seed=3, player_id="30", gamer_tag="Cid"),
    dict(seed=4, player_id="40", gamer_tag="Dot"),  # signed up in the hub data only
]


def test_plan_puts_startgg_seeds_in_the_hub_order():
    found = push.plan(ROWS, SEEDS)
    assert found["mapping"] == [
        dict(seedId="s2", seedNum=1),
        dict(seedId="s1", seedNum=2),
        dict(seedId="s3", seedNum=3),
    ]
    assert found["changes"] == [
        dict(tag="Bee", before=2, after=1),
        dict(tag="Ace", before=1, after=2),
    ]
    assert found["unchanged"] == 1 and found["not_on_startgg"] == ["Dot"]
    assert found["not_seeded"] == []
    # Same inputs, same digest; any change on either side, another one.
    assert push.plan(ROWS, SEEDS)["digest"] == found["digest"]
    moved = [dict(s, seed=4 - s["seed"]) for s in SEEDS]
    assert push.plan(ROWS, moved)["digest"] != found["digest"]


def test_entrants_without_hub_seed_go_last_and_block_the_upload():
    found = push.plan(ROWS[:2], SEEDS)
    assert found["mapping"][-1] == dict(seedId="s3", seedNum=3)
    assert found["not_seeded"] == ["Cid"]
    with pytest.raises(push.Blocked, match="no tienen seed en el hub"):
        push.check(found, enabled=True, typed="cs", expected_text="cs", digest=found["digest"])


@pytest.mark.parametrize(
    "kwargs, reason",
    [
        (dict(enabled=False), "apagado"),
        (dict(typed="otro"), "escribir exactamente «cs»"),
        (dict(digest="0" * 16), "cambiaron desde que revisaste"),
    ],
)
def test_every_guard_must_pass(kwargs, reason):
    found = push.plan(ROWS, SEEDS)
    args = dict(enabled=True, typed=" cs ", expected_text="cs", digest=found["digest"]) | kwargs
    with pytest.raises(push.Blocked, match=reason):
        push.check(found, **args)
    push.check(found, enabled=True, typed=" cs ", expected_text="cs", digest=found["digest"])


def test_nothing_to_upload_when_startgg_already_matches():
    same = [dict(seed=s["seed"], player_id=s["player_id"], gamer_tag=s["tag"]) for s in SEEDS]
    found = push.plan(same, SEEDS)
    with pytest.raises(push.Blocked, match="nada que subir"):
        push.check(found, enabled=True, typed="cs", expected_text="cs", digest=found["digest"])


def test_verify_reports_seeds_that_did_not_land():
    mapping = push.plan(ROWS, SEEDS)["mapping"]
    numbers = {m["seedId"]: m["seedNum"] for m in mapping}
    assert push.verify(mapping, [dict(s, seed=numbers[s["id"]]) for s in SEEDS]) == []
    wrong = push.verify(mapping, SEEDS)
    assert [(w["tag"], w["expected"], w["found"]) for w in wrong] == [("Bee", 1, 2), ("Ace", 2, 1)]


def client_with_writes(db, enabled):
    from accounts import LEGACY_EXPIRES

    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        admin_token_expires=LEGACY_EXPIRES,
        startgg_api_token=SecretStr("t"),
        startgg_seeding_writes=enabled,
    )
    from fastapi.testclient import TestClient

    return TestClient(create_app(settings, engine=db))


def test_upload_flow_reviews_confirms_writes_and_verifies(project, monkeypatch):
    with client_for(project) as client:
        rows = client.get("/api/v1/seeding/cs", headers=AUTH).json()["seeds"]
    # start.gg has the same players in reverse order.
    state = {
        "seeds": [
            dict(id=f"s{i}", seed=len(rows) - i + 1, player_id=r["player_id"], tag=r["gamer_tag"])
            for i, r in enumerate(rows, 1)
        ]
    }
    phase = dict(id="77", name="Pools")
    written = []

    async def read(client, event_slug):
        return phase, [dict(s) for s in state["seeds"]]

    async def write(client, phase_, mapping):
        written.append(mapping)
        numbers = {m["seedId"]: m["seedNum"] for m in mapping}
        state["seeds"] = [dict(s, seed=numbers[s["id"]]) for s in state["seeds"]]

    monkeypatch.setattr(push, "read", read)
    monkeypatch.setattr(push, "write", write)
    with client_with_writes(project, enabled=False) as client:
        preview = client.get("/api/v1/seeding/cs/startgg", headers=AUTH).json()
        assert preview["enabled"] is False and preview["confirm_text"] == "cs"
        body = dict(digest=preview["digest"], confirm="cs")
        r = client.post("/api/v1/seeding/cs/startgg", json=body, headers=AUTH)
        assert r.status_code == 409 and "apagado" in r.json()["detail"]
        assert client.post("/api/v1/seeding/cs/startgg", json=body).status_code == 401
    with client_with_writes(project, enabled=True) as client:
        preview = client.get("/api/v1/seeding/cs/startgg", headers=AUTH).json()
        assert preview["changes"]
        wrong_text = dict(digest=preview["digest"], confirm="center")
        assert (
            client.post("/api/v1/seeding/cs/startgg", json=wrong_text, headers=AUTH).status_code
            == 409
        )
        assert written == []
        ok = dict(digest=preview["digest"], confirm="cs")
        r = client.post("/api/v1/seeding/cs/startgg", json=ok, headers=AUTH).json()
        assert r["verified"] is True and r["changed"] == len(preview["changes"])
        assert len(written) == 1
        # Repeating the same confirmation is refused: start.gg changed since the review.
        again = client.post("/api/v1/seeding/cs/startgg", json=ok, headers=AUTH)
        assert again.status_code == 409 and len(written) == 1
        audit = client.get("/api/v1/seeding/cs/audit", headers=AUTH).json()
        assert any(e["action"] == "push_startgg" for e in audit)
