"""Opt-in, read-only AI assistance. No tools, execution, or autonomous writes."""

from datetime import datetime, timedelta
import hashlib
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, String, Text, Uuid, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from devhub.ai_provider import AIProvider, OpenAIResponsesProvider
from devhub.auth import require_user
from devhub.config import settings
from devhub.db import Base, get_db
from devhub.models import AuditEvent, Task, User, utcnow
from devhub.policy import organization_access, project_access, require_admin

router = APIRouter(prefix="/api/v1/organizations/{org_id}/projects/{project_id}/ai", tags=["AI assistance"])


class AISettings(Base):
    __tablename__ = "ai_settings"
    org_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"]),)


class AIRequest(Base):
    __tablename__ = "ai_requests"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    org_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    project_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    input_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(30))
    state: Mapped[str] = mapped_column(String(20), default="pending")
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"]),
        ForeignKeyConstraint(["org_id", "user_id"], ["memberships.org_id", "memberships.user_id"]),
    )


class EnableInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class GenerateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    kind: Literal["project_summary", "task_breakdown", "release_notes"]
    prompt: str = Field(default="", max_length=2000)
    include_context: bool = False


def provider_enabled():
    return bool(settings.openai_api_key and settings.openai_model)


@router.get("/settings")
def status(org_id: UUID, project_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    project_access(db, user, str(org_id), str(project_id))
    current = db.get(AISettings, (str(org_id), str(project_id)))
    return {"enabled": bool(current and current.enabled), "configured": provider_enabled()}


@router.patch("/settings")
def enable(
    org_id: UUID,
    project_id: UUID,
    body: EnableInput,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    require_admin(organization_access(db, user, str(org_id), lock=True))
    project_access(db, user, str(org_id), str(project_id))
    current = db.get(AISettings, (str(org_id), str(project_id)))
    if not current:
        current = AISettings(org_id=str(org_id), project_id=str(project_id))
        db.add(current)
    current.enabled = body.enabled
    db.add(
        AuditEvent(
            org_id=str(org_id),
            actor_id=user.id,
            action="ai.consent_changed",
            resource_id=str(project_id),
            details={"enabled": body.enabled},
        )
    )
    return {"enabled": body.enabled, "configured": provider_enabled()}


def generate_text(kind: str, prompt: str, context: dict) -> tuple[str, int]:
    provider: AIProvider = OpenAIResponsesProvider(settings.openai_api_key, settings.openai_model)
    return provider.generate(kind, prompt, context)


@router.post("/generate")
def generate(
    org_id: UUID,
    project_id: UUID,
    body: GenerateInput,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    org, project_id, request_id = str(org_id), str(project_id), str(body.request_id)
    # Serialize quota reservation with membership changes, then release all locks before network I/O.
    organization_access(db, user, org, lock=True)
    project, _ = project_access(db, user, org, project_id, write=True)
    consent = db.get(AISettings, (org, project_id))
    if not consent or not consent.enabled:
        raise HTTPException(403, "An organization administrator must enable AI for this project")
    if not provider_enabled():
        raise HTTPException(503, "Your operator has not configured an AI provider")
    digest = hashlib.sha256(body.model_dump_json(exclude={"request_id"}).encode()).hexdigest()
    previous = db.get(AIRequest, request_id)
    if previous:
        if (
            previous.org_id != org
            or previous.project_id != project_id
            or previous.user_id != user.id
            or previous.input_hash != digest
        ):
            raise HTTPException(409, "Request identifier is already in use")
        if previous.state == "succeeded":
            return {"text": previous.output, "request_id": request_id, "kind": previous.kind}
        raise HTTPException(409, "This request was already attempted; start a new request")
    daily = db.scalar(
        select(func.count())
        .select_from(AIRequest)
        .where(AIRequest.org_id == org, AIRequest.created_at > utcnow() - timedelta(days=1))
    )
    hourly = db.scalar(
        select(func.count())
        .select_from(AIRequest)
        .where(
            AIRequest.org_id == org,
            AIRequest.user_id == user.id,
            AIRequest.created_at > utcnow() - timedelta(hours=1),
        )
    )
    if daily >= 100 or hourly >= 10:
        raise HTTPException(429, "AI request limit reached. Try again later", headers={"Retry-After": "3600"})
    context = {}
    if body.include_context:
        tasks = db.scalars(
            select(Task)
            .where(Task.org_id == org, Task.project_id == project_id)
            .order_by(Task.updated_at.desc(), Task.id)
            .limit(30)
        ).all()
        context = {
            "name": project.name,
            "description": project.description[:1000],
            "latest_tasks": [
                {
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "description": t.description[:300],
                }
                for t in tasks
            ],
        }
    record = AIRequest(
        id=request_id, org_id=org, project_id=project_id, user_id=user.id, input_hash=digest, kind=body.kind
    )
    db.add(record)
    db.add(
        AuditEvent(
            org_id=org,
            actor_id=user.id,
            action="ai.requested",
            resource_id=request_id,
            details={"kind": body.kind, "include_context": body.include_context},
        )
    )
    db.commit()
    try:
        output, tokens = generate_text(body.kind, body.prompt, context)
    except HTTPException:
        from devhub.db import set_tenant

        set_tenant(db, org)
        record.state = "failed"
        db.commit()
        raise
    # Permissions might have changed while the provider was running.
    db.expire_all()
    user = require_user(request, db)
    project_access(db, user, org, project_id, write=True)
    consent = db.get(AISettings, (org, project_id))
    if not consent or not consent.enabled:
        raise HTTPException(403, "AI was disabled while this request was running")
    record = db.get(AIRequest, request_id)
    record.output, record.state, record.output_tokens = output, "succeeded", tokens
    return {"text": output, "request_id": request_id, "kind": body.kind}
