import asyncio

import pytest

from dataclasses import replace
from devhub import auth
from devhub.config import Settings
from devhub.http_limits import BodyLimitMiddleware
from fastapi.testclient import TestClient
from devhub import main


@pytest.mark.parametrize("render_host", ["", "devhub-host-test.onrender.com"])
def test_exact_render_host_allowlist(monkeypatch, render_host):
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", render_host)
    configured = Settings(
        environment="production", app_origin="https://devhub.example", dev_auth_enabled=False
    )
    configured.validate()
    monkeypatch.setattr(main, "settings", configured)
    # Host validation is independent of startup database checks; do not enter lifespan here.
    client = TestClient(main.create_app())
    try:
        for host in ("devhub.example", "localhost", "127.0.0.1", "testserver"):
            assert client.get("/health/live", headers={"Host": host}).status_code == 200
        expected = 200 if render_host else 400
        assert (
            client.get("/health/live", headers={"Host": "devhub-host-test.onrender.com"}).status_code
            == expected
        )
        for host in (
            "other-service.onrender.com",
            "devhub-host-test.onrender.com.evil.example",
            "evil.example",
        ):
            response = client.get(
                "/health/live",
                headers={"Host": host, "X-Forwarded-Host": "devhub-host-test.onrender.com"},
            )
            assert response.status_code == 400
            assert response.text == "Invalid host header"
    finally:
        client.close()


@pytest.mark.parametrize(
    "hostname",
    ["*", "*.onrender.com", "https://devhub.onrender.com", "devhub.onrender.com/", "evil.example"],
)
def test_render_host_configuration_rejects_wildcards_and_urls(hostname):
    with pytest.raises(ValueError, match="one exact onrender.com hostname"):
        Settings(render_external_hostname=hostname).validate()


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
