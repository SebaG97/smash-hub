from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import create_app


def client(engine):
    return TestClient(
        create_app(
            Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/test"),
            engine=engine,
        )
    )


def test_live_does_not_connect():
    engine = MagicMock()
    with client(engine) as c:
        assert c.get("/api/v1/health/live").json() == {"status": "alive"}
        assert c.get("/api/v1/meta").json()["version"] == "0.1.0"
        assert c.get("/api/openapi.json").status_code == 200
        assert c.post("/api/v1/meta", json={}).status_code == 405
    engine.connect.assert_not_called()


def test_ready_queries_database():
    engine = MagicMock()
    with client(engine) as c:
        assert c.get("/api/v1/health/ready").json() == {"status": "ready"}
    engine.connect.return_value.__enter__.return_value.execute.assert_called_once()


def test_ready_hides_database_error():
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("password=SECRET", {}, Exception("SECRET"))
    with client(engine) as c:
        response = c.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable"}
        assert "SECRET" not in response.text


def test_cors_denies_unknown_origins():
    with client(MagicMock()) as c:
        bad = c.options(
            "/api/v1/meta",
            headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"},
        )
        assert bad.status_code == 400
        good = c.options(
            "/api/v1/meta",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert good.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unexpected_error_is_consumed_without_secret_logging(caplog):
    app = create_app(
        Settings(_env_file=None, database_url="postgresql://unused:unused@localhost/test"),
        engine=MagicMock(),
    )

    @app.get("/test-only-error")
    def broken():
        raise RuntimeError("password=DO_NOT_LOG_ME")

    with TestClient(app) as c:
        response = c.get("/test-only-error")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
    assert "DO_NOT_LOG_ME" not in caplog.text
    assert "RuntimeError" in caplog.text
