"""Run migrations before any Render CMD override, without logging credentials."""

import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def migrate():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from devhub.config import settings

    command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")
    # Fail closed even if someone previously stamped a revision without its DDL.
    engine = create_engine(settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1))
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT link_session_hash FROM oidc_flows LIMIT 0"))
    finally:
        engine.dispose()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or not os.environ.get("DATABASE_URL"):
        print("Startup failed: command and explicit DATABASE_URL are required.", flush=True)
        return 1
    os.chdir(ROOT)
    original_role = os.environ.get("PROCESS_ROLE")
    os.environ["PROCESS_ROLE"] = "migration"
    print("Database migration: upgrading to Alembic head before starting HTTP server.", flush=True)
    try:
        migrate()
    except Exception as exc:
        # Exception messages/tracebacks can contain connection strings or SQL parameters.
        code = getattr(getattr(exc, "orig", None), "sqlstate", None)
        code = code if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code) else "unknown"
        print(f"Database migration FAILED (SQLSTATE {code}); HTTP server will not start.", flush=True)
        if code == "42501":
            print("Database role lacks migration privileges; schema-owner action is required.", flush=True)
        return 1
    finally:
        if original_role is None:
            os.environ.pop("PROCESS_ROLE", None)
        else:
            os.environ["PROCESS_ROLE"] = original_role
    print("Database migration complete; starting application.", flush=True)
    # Replace this process, preserving signals and the caller's original environment.
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    raise SystemExit(main())
