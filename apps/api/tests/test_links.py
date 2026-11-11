"""Linking accounts to player records: requests, direct links and conflicts (ADR-021)."""

from uuid import UUID

import pytest
from accounts import LEGACY_EXPIRES, WEB, make_user, sign_in
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import AuthAuditEntry
from app.core.config import Settings
from app.links.models import PlayerLink
from app.main import create_app
from app.players.models import Player

KEY = "k" * 32
VERIFIED = "Me mostró el código en su bio de start.gg"


@pytest.fixture
def client(db):
    opened = []

    def make():
        settings = Settings(
            _env_file=None,
            database_url="postgresql://unused:unused@localhost/test",
            admin_token=KEY,
            admin_token_expires=LEGACY_EXPIRES,
        )
        c = TestClient(create_app(settings, engine=db))
        c.__enter__()
        opened.append(c)
        return c

    yield make
    for c in opened:
        c.__exit__(None, None, None)


@pytest.fixture
def people(db, client):
    with Session(db, expire_on_commit=False) as s, s.begin():
        players = {tag: Player(tag=tag) for tag in ["Chag", "Wesker", "vBash"]}
        s.add_all(players.values())
    for name in ["ana", "beto"]:
        make_user(db, name)
    make_user(db, "org", role="admin")
    make_user(db, "org2", role="admin")
    sessions = {name: sign_in(client(), name) for name in ["ana", "beto", "org", "org2"]}
    ids = {name: c.get("/api/v1/auth/me").json()["user"]["id"] for name, c in sessions.items()}
    return dict(players={t: str(p.id) for t, p in players.items()}, s=sessions, ids=ids)


def test_request_reviewed_and_approved(db, people):
    ana, org, org2 = people["s"]["ana"], people["s"]["org"], people["s"]["org2"]
    chag = people["players"]["Chag"]
    found = ana.get("/api/v1/links/players", params=dict(q="cha")).json()
    assert found == [dict(id=chag, tag="Chag", linked=False)]
    assert ana.get("/api/v1/links/players", params=dict(q="%")).json() == []  # no wildcards
    ask = dict(player_id=chag, evidence="corto")
    assert ana.post("/api/v1/links/requests", json=ask, headers=WEB).status_code == 422
    ask["evidence"] = "Mi start.gg es start.gg/user/chag, Discord chag#1"
    assert ana.post("/api/v1/links/requests", json=ask).status_code == 403  # CSRF
    mine = ana.post("/api/v1/links/requests", json=ask, headers=WEB)
    assert mine.status_code == 201
    request = mine.json()["requests"][0]
    assert request["status"] == "pending" and request["code"].startswith("SH-")
    assert ana.post("/api/v1/links/requests", json=ask, headers=WEB).status_code == 409
    # A plain user cannot review.
    assert ana.get("/api/v1/admin/link-requests").status_code == 403
    queue = org.get("/api/v1/admin/link-requests").json()
    assert [(r["user"]["username"], r["player"]["tag"], r["code"]) for r in queue] == [
        ("ana", "Chag", request["code"])
    ]
    approve = f"/api/v1/admin/link-requests/{request['id']}/approve"
    # The username is not proof: the reviewer has to say how they checked.
    assert org.post(approve, json=dict(verification="ok"), headers=WEB).status_code == 422
    assert org.post(approve, json=dict(verification=VERIFIED), headers=WEB).status_code == 200
    assert org2.post(approve, json=dict(verification=VERIFIED), headers=WEB).status_code == 409
    after = ana.get("/api/v1/links/mine").json()
    assert after["player"] == dict(id=chag, tag="Chag")
    assert after["requests"][0]["status"] == "approved"
    assert ana.get("/api/v1/auth/me").json()["user"]["player"]["tag"] == "Chag"
    # The record is taken now: nobody else can ask for it, and Ana cannot ask again.
    beto = people["s"]["beto"]
    taken = beto.post(
        "/api/v1/links/requests",
        json=dict(player_id=chag, evidence="Soy Chag de verdad, preguntá"),
        headers=WEB,
    )
    assert taken.status_code == 409
    again = ana.post(
        "/api/v1/links/requests",
        json=dict(player_id=people["players"]["Wesker"], evidence="También soy Wesker, jaja"),
        headers=WEB,
    )
    assert again.status_code == 409
    with Session(db) as s:
        link = s.scalar(select(PlayerLink))
        assert (link.method, link.linked_by_name, link.verification) == ("request", "org", VERIFIED)


def test_requests_can_be_rejected_or_cancelled(db, people):
    beto, org = people["s"]["beto"], people["s"]["org"]
    wesker = people["players"]["Wesker"]
    ask = dict(player_id=wesker, evidence="Jugué el último Center Stage como Wesker")
    request = beto.post("/api/v1/links/requests", json=ask, headers=WEB).json()["requests"][0]
    reject = f"/api/v1/admin/link-requests/{request['id']}/reject"
    assert org.post(reject, json=dict(note="no"), headers=WEB).status_code == 422
    done = org.post(reject, json=dict(note="No coincide el código"), headers=WEB)
    assert done.status_code == 200
    mine = beto.get("/api/v1/links/mine").json()
    assert mine["player"] is None and mine["requests"][0]["review_note"] == "No coincide el código"
    second = beto.post("/api/v1/links/requests", json=ask, headers=WEB).json()["requests"][0]
    other = people["s"]["ana"]
    assert other.delete(f"/api/v1/links/requests/{second['id']}", headers=WEB).status_code == 404
    cancelled = beto.delete(f"/api/v1/links/requests/{second['id']}", headers=WEB)
    assert cancelled.json()["requests"][0]["status"] == "cancelled"
    assert org.get("/api/v1/admin/link-requests").json() == []


def test_nobody_reviews_or_links_their_own_account(db, people):
    org = people["s"]["org"]
    vbash = people["players"]["vBash"]
    ask = dict(player_id=vbash, evidence="Soy vBash, cualquiera del local me conoce")
    request = org.post("/api/v1/links/requests", json=ask, headers=WEB).json()["requests"][0]
    approve = f"/api/v1/admin/link-requests/{request['id']}/approve"
    assert org.post(approve, json=dict(verification=VERIFIED), headers=WEB).status_code == 403
    direct = dict(user_id=people["ids"]["org"], player_id=vbash, verification=VERIFIED)
    assert org.post("/api/v1/admin/links", json=direct, headers=WEB).status_code == 403
    # Another administrator can.
    org2 = people["s"]["org2"]
    assert org2.post(approve, json=dict(verification=VERIFIED), headers=WEB).status_code == 200


def test_direct_links_conflicts_and_audited_replacement(db, people):
    org = people["s"]["org"]
    chag, wesker = people["players"]["Chag"], people["players"]["Wesker"]
    ana_id, beto_id = people["ids"]["ana"], people["ids"]["beto"]
    # Plain users and the legacy key cannot link.
    body = dict(user_id=ana_id, player_id=chag, verification=VERIFIED)
    assert (
        people["s"]["beto"].post("/api/v1/admin/links", json=body, headers=WEB).status_code == 403
    )
    assert (
        people["s"]["beto"]
        .post(
            "/api/v1/admin/links",
            json=body,
            headers={"Authorization": f"Bearer {KEY}", **WEB},
        )
        .status_code
        == 403
    )
    found = org.get("/api/v1/admin/users", params=dict(q="an")).json()
    assert [u["username"] for u in found] == ["ana"]
    assert org.post("/api/v1/admin/links", json=body, headers=WEB).status_code == 201
    assert org.post("/api/v1/admin/links", json=body, headers=WEB).status_code == 409
    # Beto on the same record: a conflict, unless replaced explicitly with a reason.
    steal = dict(user_id=beto_id, player_id=chag, verification=VERIFIED)
    assert org.post("/api/v1/admin/links", json=steal, headers=WEB).status_code == 409
    steal["replace"] = True
    assert org.post("/api/v1/admin/links", json=steal, headers=WEB).status_code == 422
    steal["reason"] = "Ana se había vinculado por error"
    assert org.post("/api/v1/admin/links", json=steal, headers=WEB).status_code == 201
    links = org.get("/api/v1/admin/links").json()
    assert [(row["user"]["username"], row["player"]["tag"]) for row in links] == [("beto", "Chag")]
    # Ana can be linked to another record; history keeps the ended link with its reason.
    again = dict(user_id=ana_id, player_id=wesker, verification=VERIFIED)
    assert org.post("/api/v1/admin/links", json=again, headers=WEB).status_code == 201
    with Session(db) as s:
        ended = s.scalar(select(PlayerLink).where(PlayerLink.unlinked_at.is_not(None)))
        assert ended.unlink_reason == "Reemplazada: Ana se había vinculado por error"
        assert ended.unlinked_by_name == "org"
        assert (
            s.scalar(
                select(func.count()).select_from(PlayerLink).where(PlayerLink.unlinked_at.is_(None))
            )
            == 2
        )
        actions = list(
            s.scalars(
                select(AuthAuditEntry.action)
                .where(AuthAuditEntry.action.like("link_%"))
                .order_by(AuthAuditEntry.created_at)
            )
        )
        assert actions.count("link_created") == 3 and actions.count("link_replaced") == 1
    # Unlinking needs a reason and frees the record.
    link_id = next(
        row["id"]
        for row in org.get("/api/v1/admin/links").json()
        if row["player"]["tag"] == "Wesker"
    )
    unlink = f"/api/v1/admin/links/{link_id}/unlink"
    assert org.post(unlink, json=dict(reason="x"), headers=WEB).status_code == 422
    assert org.post(unlink, json=dict(reason="Lo pidió Ana"), headers=WEB).status_code == 200
    assert org.post(unlink, json=dict(reason="Lo pidió Ana"), headers=WEB).status_code == 404
    assert people["s"]["ana"].get("/api/v1/links/mine").json()["player"] is None


def test_database_forbids_two_active_links_for_one_player(db, people):
    from sqlalchemy.exc import IntegrityError

    chag = people["players"]["Chag"]
    with Session(db) as s, pytest.raises(IntegrityError), s.begin():
        for name in ["ana", "beto"]:
            s.add(
                PlayerLink(
                    user_id=UUID(people["ids"][name]),
                    player_id=UUID(chag),
                    method="admin",
                    verification=VERIFIED,
                    linked_by_name="org",
                )
            )
            s.flush()
