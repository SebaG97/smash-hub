"""Synthetic regression cases; no actual competitor data."""

import copy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_startgg import prepare, run
from test_startgg import snapshot as snapshot

from app.competitions.models import Set
from app.core.config import Settings
from app.integrations.startgg.service import normalized_result
from app.integrations.startgg.snapshot import Result
from app.main import create_app


def raw_result(**changes):
    data = {
        "id": "test",
        "state": 3,
        "round": 2,
        "fullRoundText": "Final",
        "completedAt": 1700000000,
        "startedAt": None,
        "winnerId": 11,
        "hasPlaceholder": False,
        "phaseGroup": {"id": "group", "bracketType": "DOUBLE_ELIMINATION"},
        "displayScore": "2 - 0",
        "slots": [
            {
                "slotIndex": 0,
                "entrant": {"id": "11"},
                "standing": {"stats": {"score": {"value": 2}}},
            },
            {
                "slotIndex": 1,
                "entrant": {"id": "12"},
                "standing": {"stats": {"score": {"value": 0}}},
            },
        ],
    }
    data.update(changes)
    return data


def unused_reset_raw():
    return raw_result(
        id="reset",
        state=5,
        round=3,
        fullRoundText="Grand Final Reset",
        completedAt=None,
        winnerId=None,
        displayScore=None,
        slots=[
            {
                "slotIndex": n,
                "entrant": None,
                "standing": None,
                "prereqType": "set",
                "prereqId": "final",
                "prereqPlacement": n + 1,
            }
            for n in range(2)
        ],
    )


def normalize(data, parent=None):
    result = Result.model_validate(data)
    parents = {"final": Result.model_validate(parent)} if parent else {}
    return normalized_result(
        result,
        {"11": SimpleNamespace(id="internal-a"), "12": SimpleNamespace(id="internal-b")},
        parents,
    )


@pytest.mark.parametrize(
    "kind, lifecycle, resolution, eligible",
    [
        ("played", "completed", "played", True),
        ("dq", "completed", "dq", False),
        ("bye", "completed", "bye", False),
        ("empty_byes", "not_played", "placeholder", False),
        ("one_unassigned", "not_played", "placeholder", False),
        ("unused_reset", "not_played", "conditional_unused", False),
        ("unused_reset_same_round", "not_played", "conditional_unused", False),
        ("played_reset", "completed", "played", True),
        ("reset_name_only", "pending", "unresolved", False),
        ("no_scores", "completed", "unresolved", False),
        ("actual_pending", "pending", "unresolved", False),
        ("in_progress", "in_progress", "unresolved", False),
        ("provider_placeholder", "completed", "placeholder", False),
    ],
)
def test_evidence_classification(kind, lifecycle, resolution, eligible):
    data, parent = raw_result(), None
    if kind == "dq":
        data["displayScore"] = "DQ"
        data["slots"][1]["standing"]["stats"]["score"]["value"] = -1
    elif kind == "bye":
        data["displayScore"] = "BYE"
        data["slots"][1] = {"entrant": None, "standing": None, "prereqType": "bye"}
    elif kind in {"empty_byes", "one_unassigned"}:
        data.update(state=1, winnerId=None, completedAt=None, displayScore=None)
        data["slots"] = [{"entrant": None, "standing": None, "prereqType": "bye"} for _ in range(2)]
        if kind == "one_unassigned":
            data["slots"][0] = {"entrant": {"id": "11"}, "standing": None}
    elif kind in {"unused_reset", "unused_reset_same_round"}:
        data, parent = unused_reset_raw(), raw_result(id="final")
        if kind == "unused_reset_same_round":
            data["round"] = parent["round"]
    elif kind == "played_reset":
        data.update(fullRoundText="Grand Final Reset", round=3)
    elif kind in {"reset_name_only", "actual_pending", "in_progress"}:
        data.update(state=2 if kind == "in_progress" else 1, completedAt=None, winnerId=None)
        if kind == "reset_name_only":
            data["fullRoundText"] = "Grand Final Reset"
    elif kind == "no_scores":
        for slot in data["slots"]:
            slot["standing"] = None
    elif kind == "provider_placeholder":
        data["hasPlaceholder"] = True
    values, sides = normalize(data, parent)
    assert values["lifecycle_status"] == lifecycle
    assert values["resolution"] == resolution
    assert values["stats_eligible"] is eligible
    assert values["ranking_eligible"] is eligible
    assert values["normalization_version"] == 2
    assert values["source_result"]["state"] == data["state"]
    assert values["source_result"]["winnerId"] == data["winnerId"]
    if data["state"] != 3:
        assert all(side["score"] is None and not side["is_winner"] for side in sides)
    if kind == "no_scores":
        assert values["status"] == "incomplete" and sides[0]["is_winner"]
        assert all(side["score"] is None for side in sides)


@pytest.mark.parametrize(
    "mutation",
    [
        "no_parent",
        "wrong_parent_state",
        "wrong_group",
        "wrong_round",
        "no_dependency",
        "started",
        "result_present",
    ],
)
def test_reset_requires_structural_evidence(mutation):
    data, parent = unused_reset_raw(), raw_result(id="final")
    if mutation == "no_parent":
        parent = None
    elif mutation == "wrong_parent_state":
        parent["state"] = 1
    elif mutation == "wrong_group":
        parent["phaseGroup"]["id"] = "other"
    elif mutation == "wrong_round":
        data["round"] = 99
    elif mutation == "no_dependency":
        data["slots"][1]["prereqId"] = "other"
    elif mutation == "started":
        data["startedAt"] = 1700000001
    elif mutation == "result_present":
        data["winnerId"] = 11
    values, _ = normalize(data, parent)
    assert values["resolution"] != "conditional_unused"
    assert not values["stats_eligible"] and not values["ranking_eligible"]


def test_missing_date_can_be_played_but_not_ranking_eligible():
    values, _ = normalize(raw_result(completedAt=None))
    assert values["stats_eligible"] and not values["ranking_eligible"]


def test_persistence_and_public_views_separate_bracket_entries(db, snapshot):
    prepare(db)
    source = copy.deepcopy(snapshot)
    source["events"][0]["sets"].append(
        raw_result(
            id="empty-bye",
            state=1,
            winnerId=None,
            completedAt=None,
            displayScore=None,
            slots=[{"entrant": None, "standing": None, "prereqType": "bye"} for _ in range(2)],
        )
    )
    final = source["events"][0]["sets"][0]
    final.update(round=2, phaseGroup={"id": "group", "bracketType": "DOUBLE_ELIMINATION"})
    reset = unused_reset_raw()
    for slot in reset["slots"]:
        slot["prereqId"] = str(final["id"])
    source["events"][0]["sets"].append(reset)
    run(db, source)
    repeated = run(db, source)
    assert repeated["counts"]["created"] == repeated["counts"]["updated"] == 0
    with Session(db) as s:
        event_id = s.scalar(select(Set.event_id).where(Set.round_label == "Final"))
    with TestClient(
        create_app(
            Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/x"),
            engine=db,
        )
    ) as c:
        main = c.get(f"/api/v1/events/{event_id}/sets").json()
        assert main["total"] == 6
        assert all(
            row["resolution"] not in {"placeholder", "conditional_unused"} for row in main["items"]
        )
        bracket = c.get(f"/api/v1/events/{event_id}/sets?view=bracket").json()
        assert bracket["total"] == 2
        assert {row["resolution"] for row in bracket["items"]} == {
            "placeholder",
            "conditional_unused",
        }
        assert all(
            row["status"] == "not_played" and not row["stats_eligible"] for row in bracket["items"]
        )
        pending = c.get(f"/api/v1/events/{event_id}/sets?status=pending&view=all").json()
        assert pending["total"] == 1
        byes = c.get(f"/api/v1/events/{event_id}/sets?resolution=bye").json()
        assert byes["total"] == 1 and byes["items"][0]["status"] == "completed"
        assert not byes["items"][0]["stats_eligible"]
        assert c.get(f"/api/v1/events/{event_id}/sets?view=unsupported").status_code == 422


def test_0003_upgrade_with_existing_results_and_reclassification(db, snapshot):
    from alembic import command
    from alembic.config import Config

    from app.competitions.models import SetSide

    prepare(db)
    run(db, snapshot)
    with Session(db) as s:
        before = {m.id: (m.status, m.source_result, m.completed_at) for m in s.scalars(select(Set))}
        sides = {
            side.id: (side.entrant_id, side.score, side.is_winner)
            for side in s.scalars(select(SetSide))
        }
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "0002")
    command.upgrade(cfg, "0003")
    with Session(db) as s:
        assert all(
            not m.stats_eligible and not m.ranking_eligible and m.normalization_version == 0
            for m in s.scalars(select(Set))
        )
        assert {
            m.id: (m.status, m.source_result, m.completed_at) for m in s.scalars(select(Set))
        } == before
    # Later migrations (0004+) add tables the importer writes; re-import at head.
    command.upgrade(cfg, "head")
    # Matching source fingerprints must not skip unverified migration backfills.
    run(db, snapshot)
    with Session(db) as s:
        assert all(m.normalization_version == 2 for m in s.scalars(select(Set)))
        assert s.scalar(select(Set.stats_eligible).where(Set.round_label == "Final"))
        assert {
            side.id: (side.entrant_id, side.score, side.is_winner)
            for side in s.scalars(select(SetSide))
        } == sides
        assert {
            m.id: (m.status, m.source_result, m.completed_at) for m in s.scalars(select(Set))
        } == before


@pytest.mark.parametrize("inconsistent", [False, True])
def test_download_fetches_invalid_sets_explicitly(snapshot, inconsistent):
    import asyncio
    import json
    from unittest.mock import AsyncMock

    import httpx
    from pydantic import SecretStr

    from app.integrations.startgg.client import ImportFailure, StartGGClient

    seen = set()

    def handler(request):
        body = json.loads(request.content)
        name = body["query"].split()[1].split("(")[0].lower()
        variables = body["variables"]
        if name == "tournament":
            data = {"tournament": snapshot["tournament"]}
        elif name == "event":
            data = {"event": next(e for e in snapshot["events"] if str(e["id"]) == variables["id"])}
        else:
            root = "tournament" if name == "participants" else "event"
            rows = (
                snapshot["participants"]
                if name == "participants"
                else next(e for e in snapshot["events"] if str(e["id"]) == variables["id"])[name]
            )
            if name == "sets" and variables.get("states") == [5]:
                seen.add(variables["id"])
                rows = [unused_reset_raw()] if variables["id"] == "10" else []
                if inconsistent and rows:
                    rows = [copy.deepcopy(snapshot["events"][0]["sets"][0])]
                    rows[0]["winnerId"] = None
            data = {
                root: {
                    name: {
                        "pageInfo": {"total": len(rows), "totalPages": int(bool(rows))},
                        "nodes": rows,
                    }
                }
            }
        return httpx.Response(200, json={"data": data})

    async def exercise():
        async with StartGGClient(
            SecretStr("TEST_ONLY"), transport=httpx.MockTransport(handler), sleep=AsyncMock()
        ) as c:
            if inconsistent:
                with pytest.raises(ImportFailure, match="inconsistent_set_snapshot"):
                    await c.download("synthetic")
            else:
                result = await c.download("synthetic")
                assert seen == {"10", "20"}
                assert len(result["events"][0]["sets"]) == 7
                assert result["events"][0]["sets"][-1]["state"] == 5

    asyncio.run(exercise())
