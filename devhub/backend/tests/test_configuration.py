import asyncio

import pytest

from dataclasses import replace
from devhub import auth
from devhub.config import Settings
from devhub.http_limits import BodyLimitMiddleware


def test_production_configuration_fails_closed(monkeypatch):
    values = dict(
        environment="production",
        app_origin="https://devhub.example",
        dev_auth_enabled=False,
        github_client_id="",
        github_client_secret="",
    )
    configured = Settings(**values)
    configured.validate()
    monkeypatch.setattr(auth, "settings", configured)
    assert auth.auth_mode() == "unconfigured"
    monkeypatch.setattr(auth, "settings", replace(configured, github_client_id="client"))
    assert auth.auth_mode() == "unconfigured"
    monkeypatch.setattr(
        auth,
        "settings",
        replace(
            configured,
            github_client_id="client",
            github_client_secret="configured",  # pragma: allowlist secret -- synthetic test fixture
        ),
    )
    assert auth.auth_mode() == "github"
    Settings(**values, process_role="worker").validate()
    with pytest.raises(ValueError, match="forbidden"):
        Settings(**dict(values, dev_auth_enabled=True), process_role="worker").validate()
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(**dict(values, app_origin="http://devhub.example"), process_role="worker").validate()


def test_chunked_body_cannot_bypass_size_limit():
    messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"456", "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    async def application(*args):
        pytest.fail("Oversized request reached the application")

    asyncio.run(BodyLimitMiddleware(application, max_bytes=5)({"type": "http"}, receive, send))
    assert sent[0]["status"] == 413
