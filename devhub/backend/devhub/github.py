"""Administrator-only GitHub metadata and durable signed webhook ingestion."""

import hashlib
import hmac
import json
import time
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
import jwt
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from devhub.auth import require_user
from devhub.config import settings
from devhub.db import get_db, set_tenant
from devhub.github_models import Installation, Repository, WebhookDelivery
from devhub.models import AuditEvent, OutboxEvent, User, utcnow
from devhub.policy import organization_access, project_access, require_admin

router = APIRouter(prefix="/api/v1", tags=["GitHub"])
API = "https://api.github.com"


class InstallationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installation_id: int = Field(gt=0)


class RepositoryInput(InstallationInput):
    repository_id: int = Field(gt=0)


def configured() -> bool:
    return bool(settings.github_app_id and settings.github_private_key)


def app_token() -> str:
    if not configured():
        raise HTTPException(503, "A GitHub App has not been configured by the operator")
    now = int(time.time())
    try:
        return jwt.encode(
            {"iat": now - 30, "exp": now + 540, "iss": settings.github_app_id},
            settings.github_private_key,
            algorithm="RS256",
        )
    except (ValueError, jwt.PyJWTError) as exc:
        raise HTTPException(503, "GitHub App credentials are unavailable") from exc


def github_request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    """Only constant API origin and internally constructed numeric-ID paths are accepted."""
    try:
        with httpx.Client(timeout=httpx.Timeout(10, connect=3), follow_redirects=False) as client:
            result = client.request(
                method,
                API + path,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10",
                },
            )
        if result.status_code in (401, 403, 404):
            raise HTTPException(502, "GitHub denied access; check installation permissions")
        result.raise_for_status()
        payload = result.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected provider response")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "GitHub is temporarily unavailable") from exc


def verify_installation(installation_id: int) -> dict:
    payload = github_request("GET", f"/app/installations/{installation_id}", app_token())
    if payload.get("id") != installation_id or payload.get("suspended_at"):
        raise HTTPException(422, "Installation is missing or suspended")
    if not isinstance(payload.get("account", {}).get("login"), str):
        raise HTTPException(502, "GitHub returned an invalid installation")
    return payload


def fetch_repository(installation_id: int, repository_id: int) -> dict:
    access = github_request(
        "POST",
        f"/app/installations/{installation_id}/access_tokens",
        app_token(),
        {"repository_ids": [repository_id], "permissions": {"metadata": "read"}},
    )
    token = access.get("token")
    if not isinstance(token, str):
        raise HTTPException(502, "GitHub returned an invalid installation credential")
    data = github_request("GET", f"/repositories/{repository_id}", token)
    if data.get("id") != repository_id or not isinstance(data.get("full_name"), str):
        raise HTTPException(502, "GitHub returned an invalid repository")
    # Construct canonical links rather than rendering arbitrary provider URLs.
    full_name = data["full_name"]
    parts = full_name.split("/")
    if len(parts) != 2 or any(not part or not all(c.isalnum() or c in "._-" for c in part) for part in parts):
        raise HTTPException(502, "GitHub returned an invalid repository name")
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "default_branch": str(data.get("default_branch") or "main")[:250],
        "open_issues_count": max(0, int(data.get("open_issues_count", 0))),
    }


def admin_access(db: Session, user: User, org_id: str) -> None:
    require_admin(organization_access(db, user, org_id))


def installation_out(item: Installation) -> dict:
    return {
        "installation_id": item.installation_id,
        "account_login": item.account_login,
        "enabled": item.enabled,
        "verified": item.verified,
    }


def repository_out(item: Repository) -> dict:
    return {
        field: getattr(item, field)
        for field in (
            "id",
            "installation_id",
            "repository_id",
            "full_name",
            "html_url",
            "default_branch",
            "open_issues_count",
            "sync_state",
            "last_synced_at",
        )
    }


@router.get("/organizations/{org_id}/github/installations")
def installations(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    admin_access(db, user, str(org_id))
    rows = db.scalars(select(Installation).where(Installation.org_id == str(org_id)).limit(100)).all()
    return {"items": [installation_out(row) for row in rows], "total": len(rows), "configured": configured()}


@router.post("/organizations/{org_id}/github/installations", status_code=201)
def register_installation(
    org_id: UUID, body: InstallationInput, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    org = str(org_id)
    admin_access(db, user, org)
    bindings = dict(
        part.strip().split(":", 1) for part in settings.github_installation_bindings.split(",") if ":" in part
    )
    if bindings.get(str(body.installation_id)) != org:
        raise HTTPException(403, "The operator must bind this GitHub installation to this organization first")
    data = verify_installation(body.installation_id)
    existing = db.get(Installation, body.installation_id)
    if existing and existing.org_id != org:
        raise HTTPException(409, "Installation is already linked")
    item = existing or Installation(installation_id=body.installation_id, org_id=org)
    item.account_login, item.enabled, item.verified = data["account"]["login"], True, True
    db.add(item)
    db.add(
        AuditEvent(
            org_id=org,
            actor_id=user.id,
            action="github.installation.linked",
            resource_id=str(body.installation_id),
        )
    )
    db.flush()
    return installation_out(item)


@router.get("/organizations/{org_id}/projects/{project_id}/repositories")
def repositories(
    org_id: UUID, project_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    org, project = str(org_id), str(project_id)
    admin_access(db, user, org)
    project_access(db, user, org, project)
    rows = db.scalars(
        select(Repository)
        .join(Installation, Repository.installation_id == Installation.installation_id)
        .where(
            Repository.org_id == org,
            Repository.project_id == project,
            Installation.enabled.is_(True),
            Repository.sync_state != "revoked",
        )
        .order_by(Repository.created_at, Repository.id)
        .limit(100)
    ).all()
    return {"items": [repository_out(row) for row in rows], "total": len(rows)}


@router.post("/organizations/{org_id}/projects/{project_id}/repositories", status_code=201)
def link_repository(
    org_id: UUID,
    project_id: UUID,
    body: RepositoryInput,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    org, project = str(org_id), str(project_id)
    admin_access(db, user, org)
    project_access(db, user, org, project, maintain=True)
    installation = db.get(Installation, body.installation_id)
    if (
        not installation
        or installation.org_id != org
        or not installation.enabled
        or not installation.verified
    ):
        raise HTTPException(404, "Active installation not found")
    data = fetch_repository(body.installation_id, body.repository_id)
    item = Repository(
        org_id=org,
        project_id=project,
        installation_id=body.installation_id,
        repository_id=body.repository_id,
        last_synced_at=utcnow(),
        **data,
    )
    db.add(item)
    db.flush()
    db.add(AuditEvent(org_id=org, actor_id=user.id, action="github.repository.linked", resource_id=item.id))
    return repository_out(item)


def queue_sync(db: Session, item: Repository, dedupe: str | None = None) -> None:
    key = dedupe or f"manual:{uuid4()}"
    inserted = db.scalar(
        insert(OutboxEvent)
        .values(
            id=str(uuid4()),
            org_id=item.org_id,
            kind="github.sync",
            payload={"repository_id": item.id},
            dedupe_key=key,
            state="pending",
            attempts=0,
            next_retry_at=utcnow(),
            created_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(OutboxEvent.id)
    )
    if inserted:
        item.sync_state = "pending"


@router.post(
    "/organizations/{org_id}/projects/{project_id}/repositories/{repository_id}/sync", status_code=202
)
def synchronize(
    org_id: UUID,
    project_id: UUID,
    repository_id: UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    org, project = str(org_id), str(project_id)
    admin_access(db, user, org)
    project_access(db, user, org, project)
    item = db.scalar(
        select(Repository).where(
            Repository.id == str(repository_id), Repository.org_id == org, Repository.project_id == project
        )
    )
    installation = db.get(Installation, item.installation_id) if item else None
    if not item or not installation or not installation.enabled:
        raise HTTPException(404, "Repository not found")
    queue_sync(db, item, f"manual:{item.id}:{int(time.time()) // 60}")
    return {"status": "queued"}


@router.post("/webhooks/github", status_code=202)
async def webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.github_webhook_secret:
        raise HTTPException(503, "Webhook is not configured")
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 1_048_576:
            raise HTTPException(413, "Webhook exceeds 1 MiB")
    digest = (
        "sha256=" + hmac.new(settings.github_webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
    )
    signature = request.headers.get("x-hub-signature-256", "")
    if not hmac.compare_digest(digest, signature):
        raise HTTPException(401, "Invalid webhook signature")
    delivery_id, event = (
        request.headers.get("x-github-delivery", ""),
        request.headers.get("x-github-event", ""),
    )
    if not delivery_id or len(delivery_id) > 100 or len(event) > 80:
        raise HTTPException(422, "Missing or invalid delivery headers")
    try:
        body = json.loads(payload)
        installation_id = int(body.get("installation", {}).get("id", 0))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, "Invalid webhook body") from exc
    installation = db.get(Installation, installation_id)
    if not installation:
        return {"status": "ignored"}
    set_tenant(db, installation.org_id)
    # Persist only routing information, never arbitrary source content from the payload.
    minimal = {"action": str(body.get("action", ""))[:80]}
    inserted = db.execute(
        insert(WebhookDelivery)
        .values(
            delivery_id=delivery_id,
            org_id=installation.org_id,
            installation_id=installation_id,
            event=event,
            payload=minimal,
            received_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["delivery_id"])
        .returning(WebhookDelivery.delivery_id)
    ).scalar_one_or_none()
    if not inserted:
        return {"status": "duplicate"}
    if event == "installation" and minimal["action"] in {"deleted", "suspend"}:
        installation.enabled = False
        return {"status": "disabled"}
    if not installation.enabled:
        return {"status": "ignored"}
    items = db.scalars(
        select(Repository).where(
            Repository.installation_id == installation_id, Repository.org_id == installation.org_id
        )
    ).all()
    for item in items:
        queue_sync(db, item, f"webhook:{delivery_id}:{item.id}")
    return {"status": "accepted"}
