"""Startup contract tests; no database or production credentials are accessed."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("container_start", ROOT / "scripts/container_start.py")
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


@pytest.mark.parametrize("command", [["python", "scripts/serve_free.py"], ["uvicorn", "devhub.main:app"]])
def test_migrate_precedes_default_and_override(monkeypatch, command):
    events = []
    monkeypatch.setenv("DATABASE_URL", "synthetic-url-not-used")
    monkeypatch.setenv("WORKER_DATABASE_URL", "different-synthetic-url")
    monkeypatch.setenv("PROCESS_ROLE", "api")
    monkeypatch.chdir(ROOT.parent)

    def migrate():
        assert startup.os.environ["DATABASE_URL"] == "synthetic-url-not-used"
        assert startup.os.environ["PROCESS_ROLE"] == "migration"
        assert Path.cwd() == ROOT
        events.append("migration")

    def execute(program, args):
        assert startup.os.environ["PROCESS_ROLE"] == "api"
        assert args == command and program == command[0]
        events.append("server")

    monkeypatch.setattr(startup, "migrate", migrate)
    monkeypatch.setattr(startup.os, "execvp", execute)
    startup.main(command)
    assert events == ["migration", "server"]


@pytest.mark.parametrize("sqlstate", ["42501", "28P01", "42703", None])
def test_failure_stops_and_redacts(monkeypatch, capsys, sqlstate):
    monkeypatch.setenv("DATABASE_URL", "synthetic-private-value")
    monkeypatch.delenv("PROCESS_ROLE", raising=False)
    monkeypatch.chdir(ROOT)

    def fail():
        error = RuntimeError("synthetic-private-value password must not appear")
        error.orig = SimpleNamespace(sqlstate=sqlstate)
        raise error

    monkeypatch.setattr(startup, "migrate", fail)
    monkeypatch.setattr(startup.os, "execvp", lambda *args: pytest.fail("server started after failure"))
    assert startup.main(["uvicorn"]) == 1
    output = capsys.readouterr()
    assert "FAILED" in output.out
    assert "synthetic-private-value" not in output.out + output.err
    assert "PROCESS_ROLE" not in startup.os.environ


def test_missing_url_never_uses_local_default(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(startup, "migrate", lambda: pytest.fail("migration attempted without URL"))
    assert startup.main(["uvicorn"]) == 1


def test_image_includes_absolute_entrypoint_and_migrations():
    dockerfile = (ROOT / "Dockerfile.free").read_text()
    assert 'ENTRYPOINT ["python", "/app/scripts/container_start.py"]' in dockerfile
    assert "COPY backend ./backend" in dockerfile
    assert "COPY scripts ./scripts" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert (ROOT / "backend/alembic.ini").is_file()
    assert (ROOT / "backend/migrations/env.py").is_file()
    assert (ROOT / "backend/migrations/versions/0003_auth.py").is_file()


def test_real_migration_contains_missing_column_without_database():
    from alembic import command
    from alembic.config import Config
    from io import StringIO

    output = StringIO()
    config = Config(str(ROOT / "backend/alembic.ini"), output_buffer=output)
    command.upgrade(config, "0002_ai:head", sql=True)
    sql = output.getvalue()
    assert "ALTER TABLE oidc_flows ADD COLUMN link_session_hash VARCHAR(64)" in sql
    assert "CREATE TABLE password_credentials" in sql
    assert "0003_auth" in sql
