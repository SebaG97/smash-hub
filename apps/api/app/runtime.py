"""Runtime TLS setup for App Platform. Never invoked during builds."""

import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy.engine import make_url


def main():
    cert = os.environ.get("DATABASE_CA_CERT")
    if cert:
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False)
        with handle:
            handle.write(cert)
        path = Path(handle.name)
        path.chmod(0o600)
        os.environ["DB_CA_CERT"] = str(path)
    else:
        path = None
    try:
        if os.environ.get("ENVIRONMENT") == "production":
            for key in ("DATABASE_URL", "MIGRATION_DATABASE_URL"):
                if os.environ.get(key):
                    try:
                        url = make_url(os.environ[key]).update_query_dict(
                            {"sslmode": "verify-full"}
                        )
                    except Exception:
                        raise RuntimeError("Invalid database URL") from None
                    os.environ[key] = url.render_as_string(hide_password=False)
        if sys.argv[1:] == ["migrate"]:
            if os.environ.get("APPROVED_MIGRATION") != "0001":
                raise RuntimeError("Explicit APPROVED_MIGRATION=0001 is required")
            from alembic import command
            from alembic.config import Config

            command.upgrade(Config("alembic.ini"), "0001")
        else:
            import uvicorn

            uvicorn.run(
                "app.main:create_app",
                factory=True,
                host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")),
                access_log=False,
            )
    finally:
        if path:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
