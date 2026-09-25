"""Isolated PostgreSQL transactions using an actual non-owner runtime role."""

from dataclasses import replace
import os

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from devhub import auth
from devhub.db import get_db
from devhub.main import create_app

ORIGIN = "http://localhost:8000"


@pytest.fixture
def database():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_engine(url)
    with engine.begin() as admin:
        if not admin.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='devhub_test_runtime'")):
            admin.execute(text("CREATE ROLE devhub_test_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS"))
        admin.execute(text("GRANT USAGE ON SCHEMA public TO devhub_test_runtime"))
        admin.execute(
            text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO devhub_test_runtime")
        )
        admin.execute(text("REVOKE UPDATE, DELETE ON audit_events FROM devhub_test_runtime"))
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("SET LOCAL ROLE devhub_test_runtime"))
        factory = sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        yield factory
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def clients(database, monkeypatch):
    monkeypatch.setattr(
        auth, "settings", replace(auth.settings, environment="test", dev_auth_enabled=True, app_origin=ORIGIN)
    )
    app = create_app()

    def override():
        with database() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override
    opened = []

    def make(email="owner@example.com"):
        client = TestClient(app, base_url=ORIGIN)
        opened.append(client)
        result = client.post(
            "/auth/dev-login",
            json={"email": email, "display_name": email.split("@")[0]},
            headers={"Origin": ORIGIN},
        )
        assert result.status_code == 200, result.text
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": result.json()["csrf_token"]})
        client.user_id = result.json()["user"]["id"]
        return client

    yield make
    for client in opened:
        client.close()


@pytest.fixture
def workspace(clients):
    owner = clients()
    org = owner.post("/api/v1/organizations", json={"name": "Test team", "slug": "test-team"})
    assert org.status_code == 201, org.text
    path = f"/api/v1/organizations/{org.json()['id']}"
    project = owner.post(path + "/projects", json={"name": "Launch", "slug": "launch"})
    assert project.status_code == 201, project.text
    return owner, path, project.json()
