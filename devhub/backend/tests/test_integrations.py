from dataclasses import replace
import hashlib
import hmac
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from devhub import ai, github, worker
from devhub.db import set_tenant
from devhub.github_models import Installation, Repository, WebhookDelivery
from devhub.models import OutboxEvent


def test_github_binding_and_verified_repository(workspace, monkeypatch):
    owner, org, project = workspace
    monkeypatch.setattr(
        github,
        "settings",
        replace(
            github.settings,
            github_installation_bindings="",
            github_app_id="123",
            github_private_key="configured",
        ),
    )
    installation_path = org + "/github/installations"
    assert owner.post(installation_path, json={"installation_id": 42}).status_code == 403
    monkeypatch.setattr(
        github, "settings", replace(github.settings, github_installation_bindings=f"42:{project['org_id']}")
    )
    monkeypatch.setattr(
        github, "verify_installation", lambda ident: {"id": ident, "account": {"login": "team"}}
    )
    assert owner.post(installation_path, json={"installation_id": 42}).status_code == 201
    monkeypatch.setattr(
        github,
        "fetch_repository",
        lambda *args: {
            "full_name": "team/repo",
            "html_url": "https://github.com/team/repo",
            "default_branch": "main",
            "open_issues_count": 3,
        },
    )
    path = org + "/projects/" + project["id"] + "/repositories"
    assert owner.post(path, json={"installation_id": 42, "repository_id": 100}).status_code == 201
    assert owner.get(path).json()["items"][0]["open_issues_count"] == 3
    assert owner.post(path, json={"installation_id": 42, "repository_id": 100}).status_code == 409


def test_webhook_signature_dedup_and_installation_revocation(workspace, database, monkeypatch):
    owner, _, project = workspace
    secret = "test-webhook-secret"
    monkeypatch.setattr(github, "settings", replace(github.settings, github_webhook_secret=secret))
    with database() as db:
        db.add(Installation(installation_id=42, org_id=project["org_id"], account_login="team"))
        db.commit()
    payload = json.dumps({"installation": {"id": 42}, "action": "deleted"}).encode()
    headers = {
        "x-github-delivery": "delivery-1",
        "x-github-event": "installation",
        "x-hub-signature-256": "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest(),
    }
    assert (
        owner.post(
            "/api/v1/webhooks/github", content=payload, headers={**headers, "x-hub-signature-256": "bad"}
        ).status_code
        == 401
    )
    assert (
        owner.post("/api/v1/webhooks/github", content=payload, headers=headers).json()["status"] == "disabled"
    )
    assert (
        owner.post("/api/v1/webhooks/github", content=payload, headers=headers).json()["status"]
        == "duplicate"
    )
    with database() as db:
        set_tenant(db, project["org_id"])
        assert not db.get(Installation, 42).enabled
        assert len(db.scalars(select(WebhookDelivery)).all()) == 1


def test_worker_retry_and_sync_are_idempotent(workspace, database, monkeypatch):
    _, _, project = workspace
    monkeypatch.setattr(worker, "SessionLocal", database)
    with database() as db:
        set_tenant(db, project["org_id"])
        db.add(Installation(installation_id=42, org_id=project["org_id"], account_login="team"))
        db.flush()
        repo = Repository(
            org_id=project["org_id"],
            project_id=project["id"],
            installation_id=42,
            repository_id=100,
            full_name="team/repo",
            html_url="https://github.com/team/repo",
        )
        db.add(repo)
        db.flush()
        github.queue_sync(db, repo, "test-sync")
        github.queue_sync(db, repo, "test-sync")
        db.commit()
    monkeypatch.setattr(
        worker,
        "fetch_repository",
        lambda *args: {
            "full_name": "team/repo",
            "html_url": "https://github.com/team/repo",
            "default_branch": "main",
            "open_issues_count": 7,
        },
    )
    for _ in range(10):
        if not worker.process_one(project["org_id"]):
            break
    with database() as db:
        set_tenant(db, project["org_id"])
        assert db.get(Repository, repo.id).sync_state == "ready"
        assert db.get(Repository, repo.id).open_issues_count == 7
        jobs = db.scalars(select(OutboxEvent).where(OutboxEvent.kind == "github.sync")).all()
        assert len(jobs) == 1 and jobs[0].state == "done"
        github.queue_sync(db, db.get(Repository, repo.id), "test-sync")
        assert db.get(Repository, repo.id).sync_state == "ready"
        github.queue_sync(db, db.get(Repository, repo.id), "test-retry")
        db.commit()

    def fail(*args):
        raise HTTPException(503, "Unavailable")

    monkeypatch.setattr(worker, "fetch_repository", fail)
    assert worker.process_one(project["org_id"])
    with database() as db:
        set_tenant(db, project["org_id"])
        job = db.scalar(select(OutboxEvent).where(OutboxEvent.dedupe_key == "test-retry"))
        assert job.state == "pending" and job.attempts == 1 and job.lease_owner is None


def test_ai_consent_context_idempotency_and_quota(workspace, monkeypatch):
    owner, org, project = workspace
    path = org + "/projects/" + project["id"]
    monkeypatch.setattr(
        ai, "settings", replace(ai.settings, openai_api_key="unit-test-key", openai_model="test-model")
    )
    captured = []
    monkeypatch.setattr(
        ai,
        "generate_text",
        lambda kind, prompt, context: (captured.append(context) or "A reviewed draft", 12),
    )
    body = {"request_id": str(uuid4()), "kind": "project_summary", "include_context": True}
    assert owner.post(path + "/ai/generate", json=body).status_code == 403
    assert owner.patch(path + "/ai/settings", json={"enabled": True}).status_code == 200
    owner.post(path + "/tasks", json={"title": "Scope tests", "description": "Keep it private"})
    first = owner.post(path + "/ai/generate", json=body)
    assert first.status_code == 200, first.text
    assert captured[0]["latest_tasks"][0]["title"] == "Scope tests"
    assert owner.post(path + "/ai/generate", json=body).json()["text"] == "A reviewed draft"
    assert len(captured) == 1
    assert owner.post(path + "/ai/generate", json={**body, "prompt": "changed"}).status_code == 409
    for _ in range(9):
        assert (
            owner.post(
                path + "/ai/generate", json={**body, "request_id": str(uuid4()), "include_context": False}
            ).status_code
            == 200
        )
    assert captured[-1] == {}
    assert owner.post(path + "/ai/generate", json={**body, "request_id": str(uuid4())}).status_code == 429


def test_ai_private_project_and_viewer_never_reach_provider(workspace, clients, monkeypatch):
    owner, org, project = workspace
    viewer = clients("viewer@example.com")
    owner.post(org + "/members", json={"email": "viewer@example.com", "role": "viewer"})
    path = org + "/projects/" + project["id"] + "/ai"
    monkeypatch.setattr(
        ai, "generate_text", lambda *args: (_ for _ in ()).throw(AssertionError("Provider reached"))
    )
    assert viewer.patch(path + "/settings", json={"enabled": True}).status_code == 403
    assert (
        viewer.post(
            path + "/generate", json={"request_id": str(uuid4()), "kind": "task_breakdown"}
        ).status_code
        == 403
    )
    owner.patch(org + "/projects/" + project["id"], json={"version": 1, "visibility": "private"})
    assert viewer.get(path + "/settings").status_code == 404


def test_ai_provider_request_is_bounded_and_not_stored(monkeypatch):
    monkeypatch.setattr(
        ai, "settings", replace(ai.settings, openai_api_key="unit-test-key", openai_model="test-model")
    )
    import httpx

    def handle(request):
        data = json.loads(request.content)
        assert data["store"] is False and data["max_output_tokens"] == 1500 and "tools" not in data
        assert request.url == "https://api.openai.com/v1/responses"
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "Draft"}]}],
                "usage": {"output_tokens": 2},
            },
        )

    original = httpx.Client
    monkeypatch.setattr(
        ai.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs)
    )
    assert ai.generate_text("task_breakdown", "Design tests", {}) == ("Draft", 2)
