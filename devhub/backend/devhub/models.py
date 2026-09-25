"""Relational domain model. Tenant-aware foreign keys are deliberate."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from devhub.db import Base


def uuid_string() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    email: Mapped[str] = mapped_column(String(320), index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="membership_role"),
        Index("ix_memberships_user_active", "user_id", "active"),
    )


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    visibility: Mapped[str] = mapped_column(String(16), default="organization")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("org_id", "id", name="uq_projects_org_id"),
        UniqueConstraint("org_id", "slug", name="uq_projects_org_slug"),
        ForeignKeyConstraint(["org_id", "created_by"], ["memberships.org_id", "memberships.user_id"]),
        CheckConstraint("visibility IN ('organization', 'private')", name="project_visibility"),
        CheckConstraint("version > 0", name="project_version"),
        Index("ix_projects_org_created", "org_id", "created_at", "id"),
    )


class ProjectMember(Base):
    __tablename__ = "project_members"
    org_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"]),
        ForeignKeyConstraint(["org_id", "user_id"], ["memberships.org_id", "memberships.user_id"]),
        CheckConstraint("role IN ('maintainer', 'contributor', 'viewer')", name="project_member_role"),
    )


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    org_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    project_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    assignee_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"]),
        ForeignKeyConstraint(["org_id", "created_by"], ["memberships.org_id", "memberships.user_id"]),
        ForeignKeyConstraint(["org_id", "assignee_id"], ["memberships.org_id", "memberships.user_id"]),
        CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="task_status"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'urgent')", name="task_priority"),
        CheckConstraint("version > 0", name="task_version"),
        Index("ix_tasks_project_status_created", "org_id", "project_id", "status", "created_at", "id"),
        Index("ix_tasks_assignee", "org_id", "assignee_id"),
    )


class Discussion(Base):
    __tablename__ = "discussions"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    org_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    project_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("org_id", "project_id", "id", name="uq_discussions_org_project_id"),
        ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"]),
        ForeignKeyConstraint(["org_id", "created_by"], ["memberships.org_id", "memberships.user_id"]),
        CheckConstraint("version > 0", name="discussion_version"),
        Index("ix_discussions_project_created", "org_id", "project_id", "created_at", "id"),
    )


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    org_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    project_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    discussion_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    body: Mapped[str] = mapped_column(Text)
    author_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "project_id", "discussion_id"],
            ["discussions.org_id", "discussions.project_id", "discussions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(["org_id", "author_id"], ["memberships.org_id", "memberships.user_id"]),
        Index("ix_comments_discussion_created", "org_id", "project_id", "discussion_id", "created_at", "id"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_audit_org_created", "org_id", "created_at"),)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    kind: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        CheckConstraint("state IN ('pending', 'processing', 'done', 'dead')", name="outbox_state"),
        Index("ix_outbox_pending", "state", "next_retry_at"),
    )
