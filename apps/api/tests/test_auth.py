"""Accounts, sessions, roles and the move away from the shared admin key (ADR-021)."""

from datetime import UTC, datetime, timedelta

import pytest
from accounts import LEGACY_EXPIRES, PASSWORD, WEB, make_user, sign_in
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import passwords, service
from app.auth.models import AuthAuditEntry, PasswordResetToken, User, UserSession
from app.cli import superadmin as cli
from app.core.config import Settings
from app.main import create_app

KEY = "k" * 32
LEGACY = {"Authorization": f"Bearer {KEY}", "X-Admin-Name": "Org"}
PREFIXES = "/api/v1/prefixes"
WRONG = "no es la clave"


class Clock:
    """A clock the tests move by hand."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    for throttle in (
        service.LOGIN_PAIR,
        service.LOGIN_ACCOUNT,
        service.LOGIN_ADDRESS,
        service.RESET_FAILURES,
    ):
        monkeypatch.setattr(throttle, "clock", fake)
    return fake


def login(c, name, password=PASSWORD, ip=None):
    headers = dict(WEB, **({"do-connecting-ip": ip} if ip else {}))
    return c.post("/api/v1/auth/login", json=dict(login=name, password=password), headers=headers)


def settings(**extra):
    values = dict(
        _env_file=None,
        database_url="postgresql://unused:unused@localhost/test",
        admin_token=KEY,
        admin_token_expires=LEGACY_EXPIRES,
    )
    values.update(extra)
    return Settings(**values)


@pytest.fixture
def client(db):
    opened = []

    def make(**extra):
        c = TestClient(create_app(settings(**extra), engine=db))
        c.__enter__()
        opened.append(c)
        return c

    yield make
    for c in opened:
        c.__exit__(None, None, None)


def register(c, username="ana", email="ana@example.com", password=PASSWORD, **extra):
    return c.post(
        "/api/v1/auth/register",
        json=dict(username=username, email=email, password=password, **extra),
        headers=WEB,
    )


# Pure parts.


def test_passwords_are_argon2id_and_checked():
    hashed = passwords.hash_password(PASSWORD)
    assert hashed.startswith("$argon2id$") and PASSWORD not in hashed
    assert passwords.verify(hashed, PASSWORD)
    assert not passwords.verify(hashed, "otra frase bastante larga")
    assert not passwords.verify(None, PASSWORD)  # legacy accounts never match
    assert passwords.problem("corta") is not None
    assert passwords.problem("x" * 129) is not None
    assert passwords.problem("password123") is not None
    assert passwords.problem("aaaaaaaaaaaa") is not None
    assert passwords.problem("ana-es-la-mejor", username="ana") is not None
    assert passwords.problem("una frase bastante larga", username="ana") is None


def test_settings_bound_the_legacy_key_and_the_ip_header():
    now = datetime.now(UTC)
    assert settings().legacy_admin_active()
    assert not settings(admin_token_expires=None).legacy_admin_active()  # undated: off
    assert not settings(admin_token_expires=now - timedelta(minutes=1)).legacy_admin_active()
    with pytest.raises(ValueError):
        settings(admin_token_expires=now + timedelta(days=200))
    with pytest.raises(ValueError):
        settings(admin_token_expires=datetime(2026, 12, 1))  # no time zone
    with pytest.raises(ValueError):
        settings(client_ip_header="do-connecting-ip: x")
    assert settings().client_ip_header is None  # no header trusted by default
    assert KEY not in repr(settings())


def test_backoff_waits_grow_are_capped_and_forget():
    clock = Clock()
    b = service.Backoff(free=3, cap=8, idle=100, clock=clock)
    for _ in range(3):
        assert b.wait("k") == 0
        b.fail("k")
    assert b.wait("k") == 1  # 4th failure would come after 1 s
    clock.t += 1
    assert b.wait("k") == 0
    b.fail("k")
    assert b.wait("k") == 2
    for _ in range(10):
        clock.t += b.wait("k")
        b.fail("k")
    assert b.wait("k") == 8  # capped
    clock.t += 101
    assert b.wait("k") == 0 and "k" not in b.state  # forgotten when idle
    b.fail("k")
    b.reset("k")
    assert b.wait("k") == 0


class FakeRequest:
    def __init__(self, header, headers, peer="10.0.0.1"):
        self.headers = headers
        self.client = type("Peer", (), {"host": peer})()
        self.app = type("App", (), {})()
        self.app.state = type("State", (), {})()
        self.app.state.settings = settings(client_ip_header=header)


def test_client_address_trusts_only_the_configured_proxy_header():
    forged = {"do-connecting-ip": "1.2.3.4", "x-forwarded-for": "5.6.7.8"}
    # Without the setting no header is trusted (local, tests, any non-proxied setup).
    assert service.client_of(FakeRequest(None, forged)) == "10.0.0.1"
    assert service.client_of(FakeRequest("do-connecting-ip", forged)) == "1.2.3.4"
    # Only the last value counts: the one the proxy adds after anything the client sent.
    added = {"do-connecting-ip": "6.6.6.6, 200.1.1.1"}
    assert service.client_of(FakeRequest("do-connecting-ip", added)) == "200.1.1.1"
    for bad in ("not-an-ip", "", "1.2.3.4, x"):
        request = FakeRequest("do-connecting-ip", {"do-connecting-ip": bad})
        assert service.client_of(request) == "10.0.0.1"
    v6 = {"do-connecting-ip": "2001:db8::1"}
    assert service.client_of(FakeRequest("do-connecting-ip", v6)) == "2001:db8::1"


# Sign-up, sign-in and sessions.


def test_register_sign_in_and_sign_out(db, client):
    c = client()
    me = c.get("/api/v1/auth/me").json()
    assert me == {"user": None, "legacy_admin_key": True}
    assert (
        c.post(
            "/api/v1/auth/register",
            json=dict(username="ana", email="ana@example.com", password=PASSWORD),
        ).status_code
        == 403
    )  # no web header (CSRF)
    created = register(c, username="Ana", email="Ana@Example.com", display_name="Ana  P")
    assert created.status_code == 201
    cookie = created.headers["set-cookie"]
    assert "sh_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    assert "Secure" not in cookie  # only in production
    user = created.json()["user"]
    assert (user["username"], user["email"], user["role"], user["display_name"]) == (
        "ana",
        "ana@example.com",
        "user",
        "Ana P",
    )
    assert c.get("/api/v1/auth/me").json()["user"]["username"] == "ana"
    # Duplicates, case-insensitively.
    other = client()
    assert register(other, username="ANA", email="x@example.com").status_code == 409
    assert register(other, username="ana2", email="ANA@example.com").status_code == 409
    assert register(other, username="a", email="b@example.com").status_code == 422
    assert register(other, username="admin", email="b@example.com").status_code == 422
    assert register(other, username="bea", email="no-es-correo").status_code == 422
    assert (
        register(other, username="bea", email="b@example.com", password="corta").status_code == 422
    )
    # The public sign-up never takes a role.
    escalate = register(other, username="eve", email="eve@example.com", role="superadmin")
    assert escalate.status_code == 422
    with Session(db) as s:
        stored = s.scalar(select(User).where(User.username == "ana"))
        assert stored.role == "user" and stored.password_hash.startswith("$argon2id$")
        token_hashes = list(s.scalars(select(UserSession.token_hash)))
        assert all(len(h) == 64 for h in token_hashes)
        assert c.cookies.get("sh_session") not in token_hashes  # only its SHA-256
    # Sign in with username or e-mail; wrong password looks like an unknown account.
    fresh = client()
    bad = fresh.post(
        "/api/v1/auth/login", json=dict(login="ana", password="otra frase larga"), headers=WEB
    )
    unknown = fresh.post(
        "/api/v1/auth/login", json=dict(login="nadie", password=PASSWORD), headers=WEB
    )
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()
    assert (
        fresh.post("/api/v1/auth/login", json=dict(login="ana", password=PASSWORD)).status_code
        == 403
    )
    sign_in(fresh, "ANA@example.com")
    assert fresh.get("/api/v1/auth/sessions").json() == {"open": 2}
    assert fresh.post("/api/v1/auth/logout", headers=WEB).status_code == 204
    assert fresh.get("/api/v1/auth/me").json()["user"] is None
    assert c.get("/api/v1/auth/me").json()["user"]["username"] == "ana"  # other session lives


def test_failures_slow_down_the_attacker_not_the_owner(db, client, clock):
    make_user(db, "ana")
    c = client(client_ip_header="do-connecting-ip")
    for _ in range(5):
        assert login(c, "ana", WRONG, ip="1.1.1.1").status_code == 401
    # From that address the next try waits, growing 1 s, 2 s, 4 s...
    slowed = login(c, "ana", WRONG, ip="1.1.1.1")
    assert slowed.status_code == 429 and slowed.headers["retry-after"] == "1"
    clock.t += 1
    assert login(c, "ana", WRONG, ip="1.1.1.1").status_code == 401
    assert login(c, "ana", WRONG, ip="1.1.1.1").headers["retry-after"] == "2"
    # Refused attempts are not evaluated and do not lengthen the wait.
    for _ in range(20):
        login(c, "ana", PASSWORD, ip="1.1.1.1")
    assert login(c, "ana", WRONG, ip="1.1.1.1").headers["retry-after"] == "2"
    # The owner, from her own address, gets in right away: nothing is locked.
    assert login(c, "ana", PASSWORD, ip="2.2.2.2").status_code == 200
    with Session(db) as s:
        failed = list(
            s.scalars(select(AuthAuditEntry.details).where(AuthAuditEntry.action == "login_failed"))
        )
        assert len(failed) == 6 and failed[0] == {"ip": "1.1.1.1"}


def test_unknown_accounts_are_throttled_the_same(db, client, clock):
    make_user(db, "ana")
    c = client()
    known = [login(c, "ana", WRONG).status_code for _ in range(6)]
    unknown = [login(c, "nadie", WRONG).status_code for _ in range(6)]
    assert known == unknown == [401] * 5 + [429]


def test_a_third_party_can_only_delay_an_account_briefly(db, client, clock):
    make_user(db, "ana")
    c = client(client_ip_header="do-connecting-ip")
    # Guessing from many addresses: after 20 failures the account waits, at most 60 s.
    for n in range(40):
        clock.t += service.LOGIN_ACCOUNT.wait("ana")
        assert login(c, "ana", WRONG, ip=f"10.0.{n}.1").status_code == 401
    r = login(c, "ana", PASSWORD, ip="2.2.2.2")
    assert r.status_code == 429 and int(r.headers["retry-after"]) <= 60
    clock.t += 60
    assert login(c, "ana", PASSWORD, ip="2.2.2.2").status_code == 200
    # Her success clears the account's count.
    assert service.LOGIN_ACCOUNT.wait("ana") == 0


def test_spoofed_headers_do_not_escape_the_limit_without_a_proxy(db, client, clock):
    c = client()  # CLIENT_IP_HEADER unset: the forged header is ignored
    codes = [login(c, "nadie", WRONG, ip=f"9.9.9.{n}").status_code for n in range(6)]
    assert codes == [401] * 5 + [429]


def test_many_accounts_from_one_address_are_throttled(db, client, clock):
    c = client()
    for n in range(service.LOGIN_ADDRESS.free):
        clock.t += service.LOGIN_PAIR.wait(("testclient", f"user{n}"))
        assert login(c, f"user{n}", WRONG).status_code == 401
    assert login(c, "otra", WRONG).status_code == 429


def test_password_change_closes_other_sessions(db, client):
    make_user(db, "ana")
    phone, laptop = sign_in(client(), "ana"), sign_in(client(), "ana")
    change = dict(current_password="no es", new_password="otra frase todavía más larga")
    assert phone.put("/api/v1/auth/password", json=change, headers=WEB).status_code == 403
    change["current_password"] = PASSWORD
    assert (
        phone.put(
            "/api/v1/auth/password", json=dict(change, new_password="corta"), headers=WEB
        ).status_code
        == 422
    )
    done = phone.put("/api/v1/auth/password", json=change, headers=WEB)
    assert done.status_code == 200 and done.json() == {"closed_sessions": 1}
    assert laptop.get("/api/v1/auth/me").json()["user"] is None
    assert phone.get("/api/v1/auth/me").json()["user"]["username"] == "ana"
    sign_in(client(), "ana", "otra frase todavía más larga")
    revoked = phone.post("/api/v1/auth/sessions/revoke-others", headers=WEB)
    assert revoked.json() == {"closed_sessions": 1}


def test_sessions_expire_and_staff_sessions_are_shorter(db, client):
    make_user(db, "ana")
    make_user(db, "org", role="admin")
    c = sign_in(client(), "ana")
    sign_in(client(), "org")
    with Session(db) as s, s.begin():
        rows = s.execute(
            select(User.username, UserSession.expires_at - UserSession.created_at).join(
                UserSession, UserSession.user_id == User.id
            )
        ).all()
        lengths = {name: round(span / timedelta(days=1)) for name, span in rows}
        assert lengths == {"ana": service.SESSION_DAYS, "org": service.STAFF_SESSION_DAYS}
        for row in s.scalars(select(UserSession)):
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert c.get("/api/v1/auth/me").json()["user"] is None


def test_production_cookie_is_secure(db, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("x")
    prod = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql://u:p@db.example/x?sslmode=verify-full",
        migration_database_url="postgresql://m:p@db.example/x?sslmode=verify-full",
        db_ca_cert=str(ca),
        cors_origins=["https://hub.example"],
    )
    with TestClient(create_app(prod, engine=db), base_url="https://hub.example") as c:
        r = register(c)
        assert r.status_code == 201
        assert "Secure" in r.headers["set-cookie"] and "HttpOnly" in r.headers["set-cookie"]


# Password recovery.


def test_there_is_no_recovery_by_mail(db, client):
    c = client()
    r = c.post("/api/v1/auth/password/forgot", json=dict(email="ana@example.com"), headers=WEB)
    assert r.status_code in (404, 405)


def issue(db, client, target="ana"):
    """A superadmin issues a link for `target`; returns (superadmin client, response)."""
    if not s_exists(db, "boss"):
        make_user(db, "boss", role="superadmin")
    boss = sign_in(client(), "boss")
    target_id = id_of(db, target)
    return boss, boss.post(f"/api/v1/admin/users/{target_id}/password-reset", headers=WEB)


def s_exists(db, username):
    with Session(db) as s:
        return s.scalar(select(User.id).where(User.username == username)) is not None


def id_of(db, username):
    with Session(db) as s:
        return s.scalar(select(User.id).where(User.username == username))


def reset(c, token, password="mi frase nueva y larga"):
    return c.post(
        "/api/v1/auth/password/reset", json=dict(token=token, password=password), headers=WEB
    )


def test_superadmin_reset_link_is_one_time_and_never_leaks(db, client, caplog):
    make_user(db, "ana")
    make_user(db, "org", role="admin")
    org = sign_in(client(), "org")
    ana_id = id_of(db, "ana")
    assert org.post(f"/api/v1/admin/users/{ana_id}/password-reset", headers=WEB).status_code == 403
    assert (
        client().post(f"/api/v1/admin/users/{ana_id}/password-reset", headers=WEB).status_code
        == 401
    )
    old_session = sign_in(client(), "ana")
    boss, issued = issue(db, client)
    assert issued.status_code == 200
    assert issued.headers["cache-control"] == "no-store"
    url = issued.json()["url"]
    assert url.startswith("http://localhost:3000/recuperar/nueva#token=")  # fragment: no logs
    token = url.split("#token=")[1]
    with Session(db) as s:
        stored = s.scalar(select(PasswordResetToken.token_hash))
        assert stored != token and len(stored) == 64  # only the SHA-256
        audits = [str(d) for d in s.scalars(select(AuthAuditEntry.details))]
        assert not any(token in d for d in audits)
    assert not any(token in d["details"].__str__() for d in boss.get("/api/v1/admin/audit").json())
    # A weak password does not spend the link.
    assert reset(client(), token, "corta").status_code == 422
    done = reset(client(), token)
    assert done.status_code == 204 and done.headers["cache-control"] == "no-store"
    assert reset(client(), token).status_code == 400  # one use only
    assert old_session.get("/api/v1/auth/me").json()["user"] is None  # every session closed
    sign_in(client(), "ana", "mi frase nueva y larga")
    assert token not in caplog.text
    with Session(db) as s:
        rows = s.execute(
            select(AuthAuditEntry.action, AuthAuditEntry.details).where(
                AuthAuditEntry.action.like("password_reset%")
            )
        ).all()
        assert {a for a, _ in rows} == {"password_reset_issued", "password_reset"}
        assert dict(rows)["password_reset"] == {"issued_by": "boss"}


def test_reset_links_die_when_replaced_expired_or_their_issuer_loses_the_role(db, client):
    make_user(db, "ana")
    make_user(db, "boss2", role="superadmin")
    _, first = issue(db, client)
    _, second = issue(db, client)
    first_token = first.json()["url"].split("#token=")[1]
    second_token = second.json()["url"].split("#token=")[1]
    assert reset(client(), first_token).status_code == 400  # replaced by the second
    # boss2 demotes boss: the links boss issued stop working.
    boss2 = sign_in(client(), "boss2")
    demote = boss2.put(
        f"/api/v1/admin/users/{id_of(db, 'boss')}/role", json=dict(role="admin"), headers=WEB
    )
    assert demote.status_code == 200
    assert reset(client(), second_token).status_code == 400
    # Expired links do not work either.
    third = boss2.post(f"/api/v1/admin/users/{id_of(db, 'ana')}/password-reset", headers=WEB)
    third_token = third.json()["url"].split("#token=")[1]
    with Session(db) as s, s.begin():
        for row in s.scalars(
            select(PasswordResetToken).where(PasswordResetToken.used_at.is_(None))
        ):
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert reset(client(), third_token).status_code == 400
    # Disabling the account voids its pending link.
    fourth = boss2.post(f"/api/v1/admin/users/{id_of(db, 'ana')}/password-reset", headers=WEB)
    fourth_token = fourth.json()["url"].split("#token=")[1]
    boss2.put(
        f"/api/v1/admin/users/{id_of(db, 'ana')}/status",
        json=dict(disabled=True, reason="Cuenta comprometida"),
        headers=WEB,
    )
    boss2.put(
        f"/api/v1/admin/users/{id_of(db, 'ana')}/status",
        json=dict(disabled=False, reason="Aclarado"),
        headers=WEB,
    )
    assert reset(client(), fourth_token).status_code == 400


def test_guessing_reset_tokens_is_slowed_down(db, client, clock):
    c = client()
    codes = [reset(c, "x" * 43).status_code for _ in range(11)]
    assert codes == [400] * 10 + [429]


# Roles.


def test_roles_are_enforced_by_the_api(db, client):
    make_user(db, "ana")
    make_user(db, "org", role="admin")
    make_user(db, "boss", role="superadmin")
    anon, ana = client(), sign_in(client(), "ana")
    org, boss = sign_in(client(), "org"), sign_in(client(), "boss")
    ana_id = ana.get("/api/v1/auth/me").json()["user"]["id"]
    org_id = org.get("/api/v1/auth/me").json()["user"]["id"]
    boss_id = boss.get("/api/v1/auth/me").json()["user"]["id"]
    # Admin routes: nobody without a session, no plain user.
    assert anon.get("/api/v1/admin/users").status_code == 401
    assert ana.get("/api/v1/admin/users").status_code == 403
    assert ana.get("/api/v1/seeding/session").status_code == 403
    assert org.get("/api/v1/seeding/session").json() == {"actor": "org"}
    # Admins search accounts but do not see e-mails; superadmins do.
    assert {u["email"] for u in org.get("/api/v1/admin/users").json()} == {None}
    assert "ana@example.com" in {u["email"] for u in boss.get("/api/v1/admin/users").json()}
    # Only superadmins manage roles.
    promote = dict(role="admin")
    assert (
        ana.put(f"/api/v1/admin/users/{ana_id}/role", json=promote, headers=WEB).status_code == 403
    )
    assert (
        org.put(f"/api/v1/admin/users/{ana_id}/role", json=promote, headers=WEB).status_code == 403
    )
    assert (
        org.put(
            f"/api/v1/admin/users/{org_id}/role", json=dict(role="superadmin"), headers=WEB
        ).status_code
        == 403
    )
    assert boss.put(f"/api/v1/admin/users/{ana_id}/role", json=promote).status_code == 403  # CSRF
    assert (
        boss.put(
            f"/api/v1/admin/users/{ana_id}/role", json=dict(role="owner"), headers=WEB
        ).status_code
        == 422
    )
    done = boss.put(f"/api/v1/admin/users/{ana_id}/role", json=promote, headers=WEB)
    assert done.status_code == 200 and done.json()["role"] == "admin"
    # The role change closed Ana's sessions: she signs in again as an admin.
    assert ana.get("/api/v1/auth/me").json()["user"] is None
    ana = sign_in(client(), "ana")
    assert ana.get("/api/v1/seeding/session").json() == {"actor": "ana"}
    # Nobody changes their own role, and the last superadmin stays.
    assert (
        boss.put(
            f"/api/v1/admin/users/{boss_id}/role", json=dict(role="user"), headers=WEB
        ).status_code
        == 403
    )
    assert (
        boss.put(
            f"/api/v1/admin/users/{boss_id}/status",
            json=dict(disabled=True, reason="prueba"),
            headers=WEB,
        ).status_code
        == 403
    )
    with Session(db) as s:
        audit = s.execute(
            select(AuthAuditEntry.actor, AuthAuditEntry.details).where(
                AuthAuditEntry.action == "role_changed"
            )
        ).all()
        assert audit == [("boss", dict(before="user", after="admin", closed_sessions=1))]


def test_superadmins_are_only_removed_by_another_superadmin(db, client):
    make_user(db, "boss", role="superadmin")
    make_user(db, "boss2", role="superadmin")
    boss = sign_in(client(), "boss")
    boss2 = sign_in(client(), "boss2")
    boss2_id = boss2.get("/api/v1/auth/me").json()["user"]["id"]
    boss_id = boss.get("/api/v1/auth/me").json()["user"]["id"]
    demoted = boss.put(f"/api/v1/admin/users/{boss2_id}/role", json=dict(role="admin"), headers=WEB)
    assert demoted.status_code == 200
    # boss2 is an admin now and cannot touch boss; boss is the only superadmin left.
    boss2 = sign_in(client(), "boss2")
    assert (
        boss2.put(
            f"/api/v1/admin/users/{boss_id}/role", json=dict(role="user"), headers=WEB
        ).status_code
        == 403
    )


def test_disabled_accounts_cannot_sign_in(db, client):
    make_user(db, "ana")
    make_user(db, "boss", role="superadmin")
    ana = sign_in(client(), "ana")
    ana_id = ana.get("/api/v1/auth/me").json()["user"]["id"]
    boss = sign_in(client(), "boss")
    assert (
        boss.put(
            f"/api/v1/admin/users/{ana_id}/status", json=dict(disabled=True), headers=WEB
        ).status_code
        == 422
    )  # a reason is required
    boss.put(
        f"/api/v1/admin/users/{ana_id}/status",
        json=dict(disabled=True, reason="Spam en el Prode"),
        headers=WEB,
    )
    assert ana.get("/api/v1/auth/me").json()["user"] is None
    login = client().post(
        "/api/v1/auth/login", json=dict(login="ana", password=PASSWORD), headers=WEB
    )
    assert login.status_code == 403
    boss.put(
        f"/api/v1/admin/users/{ana_id}/status",
        json=dict(disabled=False, reason="Aclarado"),
        headers=WEB,
    )
    sign_in(client(), "ana")


# Administrative access: sessions instead of the shared key.


def test_admin_writes_are_audited_with_the_person(db, client):
    make_user(db, "org", role="admin")
    org = sign_in(client(), "org")
    rule = dict(status="hidden")
    r = org.put(f"{PREFIXES}/abc", json=rule)
    assert r.status_code == 403  # no web header: the cookie alone does not write
    org.put(f"{PREFIXES}/abc", json=rule, headers=WEB)
    with Session(db) as s:
        rows = s.execute(
            select(AuthAuditEntry.actor, AuthAuditEntry.details).where(
                AuthAuditEntry.action == "admin_request"
            )
        ).all()
    assert rows == [("org", dict(method="PUT", path=f"{PREFIXES}/abc"))]


def test_legacy_key_works_only_until_it_expires(db, client):
    live = client()
    assert live.get("/api/v1/seeding/session", headers=LEGACY).json() == {"actor": "clave:Org"}
    with Session(db) as s:
        assert (
            s.scalar(select(func.count()).where(AuthAuditEntry.action == "legacy_admin_request"))
            == 1
        )
    # It never opens account administration.
    assert live.get("/api/v1/admin/users", headers=LEGACY).status_code == 401
    expired = client(admin_token_expires=datetime.now(UTC) - timedelta(minutes=1))
    assert expired.get("/api/v1/auth/me").json()["legacy_admin_key"] is False
    r = expired.get("/api/v1/seeding/session", headers=LEGACY)
    assert r.status_code == 401 and "ya no se acepta" in r.json()["detail"]
    undated = client(admin_token_expires=None)
    assert undated.get("/api/v1/seeding/session", headers=LEGACY).status_code == 401
    # A signed-in administrator keeps working after the key is gone.
    make_user(db, "org", role="admin")
    assert sign_in(undated, "org").get("/api/v1/seeding/session").json() == {"actor": "org"}


def test_superadmin_sees_the_transition_status(db, client):
    make_user(db, "boss", role="superadmin")
    boss = sign_in(client(), "boss")
    boss.get("/api/v1/seeding/session", headers=LEGACY)  # session wins over the key
    client().get("/api/v1/seeding/session", headers=LEGACY)
    status = boss.get("/api/v1/admin/status").json()
    assert status["roles"] == {"user": 0, "admin": 0, "superadmin": 1}
    assert status["legacy_admin_key"]["active"] is True
    assert status["legacy_admin_key"]["last_used_at"] is not None
    log = boss.get("/api/v1/admin/audit", params=dict(action="legacy_admin_request")).json()
    assert [row["actor"] for row in log] == ["clave:Org"]


# The first superadmin.


def test_cli_names_the_first_superadmin_only_once(db):
    make_user(db, "seba")
    with Session(db) as s, s.begin():
        cli.promote(s, "SEBA")
    with Session(db) as s:
        assert s.scalar(select(User.role).where(User.username == "seba")) == "superadmin"
        assert (
            s.scalar(select(AuthAuditEntry.actor).where(AuthAuditEntry.action == "role_changed"))
            == "cli"
        )
    make_user(db, "otra")
    with Session(db) as s, s.begin(), pytest.raises(cli.Refused):
        cli.promote(s, "otra")
    with Session(db) as s, s.begin(), pytest.raises(cli.Refused):
        cli.create(s, "nuevo", "nuevo@example.com", PASSWORD)
    with Session(db) as s, s.begin():
        cli.promote(s, "otra", additional=True)  # deliberate recovery
    with Session(db) as s, s.begin(), pytest.raises(cli.Refused):
        cli.promote(s, "nadie", additional=True)


def test_cli_can_create_the_account_with_a_valid_password(db):
    with Session(db) as s, s.begin(), pytest.raises(cli.Refused):
        cli.create(s, "seba", "seba@example.com", "corta")
    with Session(db) as s, s.begin():
        cli.create(s, "seba", "seba@example.com", PASSWORD)
    with Session(db) as s:
        user = s.scalar(select(User).where(User.username == "seba"))
        assert user.role == "superadmin" and passwords.verify(user.password_hash, PASSWORD)
