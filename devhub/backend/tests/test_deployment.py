from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from devhub import ai, main
from devhub.ai_provider import OpenAIResponsesProvider


@pytest.mark.parametrize("key,model", [("", ""), ("", "configured-model"), ("not-a-live-key", "")])
def test_unconfigured_provider_makes_no_network_call(monkeypatch, key, model):
    def forbidden(*args, **kwargs):
        pytest.fail("Unconfigured AI attempted a network call")

    monkeypatch.setattr(httpx, "Client", forbidden)
    with pytest.raises(HTTPException) as error:
        OpenAIResponsesProvider(key, model).generate("project_summary", "", {})
    assert error.value.status_code == 503


def test_core_remains_functional_without_ai(workspace, monkeypatch):
    owner, org, project = workspace
    monkeypatch.setattr(ai, "settings", replace(ai.settings, openai_api_key="", openai_model=""))

    def forbidden(*args, **kwargs):
        pytest.fail("Missing credentials reached provider")

    monkeypatch.setattr(ai, "generate_text", forbidden)
    path = org + "/projects/" + project["id"]
    assert owner.get(path + "/ai/settings").json()["configured"] is False
    owner.patch(path + "/ai/settings", json={"enabled": True})
    for kind in ("project_summary", "task_breakdown", "release_notes"):
        response = owner.post(path + "/ai/generate", json={"request_id": str(uuid4()), "kind": kind})
        assert response.status_code == 503
    assert owner.post(path + "/tasks", json={"title": "Works without AI"}).status_code == 201
    assert owner.get(path + "/tasks").json()["total"] == 1


def test_single_origin_static_hosting_preserves_api_boundary(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text('<html><script src="/assets/app.js"></script></html>')
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_text('console.log("loaded")')
    monkeypatch.setattr(main, "settings", replace(main.settings, frontend_dist=str(tmp_path)))
    client = TestClient(main.create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/api/v1/missing").status_code == 404
    assert client.get("/.env").status_code == 404


def test_demo_limit_does_not_block_readiness():
    from fastapi import FastAPI
    from devhub.http_limits import DemoRateLimitMiddleware

    app = FastAPI()
    app.add_middleware(DemoRateLimitMiddleware, mutation_limit=1)

    @app.post("/test")
    def write():
        return {"ok": True}

    @app.get("/health/live")
    def live():
        return {"ok": True}

    client = TestClient(app)
    assert client.post("/test").status_code == 200
    limited = client.post("/test")
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0
    assert client.get("/health/live").status_code == 200
