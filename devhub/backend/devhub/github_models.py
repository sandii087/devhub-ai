"""GitHub metadata only: no source code, personal tokens, or repository writes."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from devhub.db import Base
from devhub.models import utcnow, uuid_string


class Installation(Base):
    __tablename__ = "github_installations"
    installation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    account_login: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("org_id", "installation_id", name="uq_installation_org_id"),)


class Repository(Base):
    __tablename__ = "github_repositories"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uuid_string)
    org_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    project_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    installation_id: Mapped[int] = mapped_column(BigInteger)
    repository_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(250))
    html_url: Mapped[str] = mapped_column(String(500))
    default_branch: Mapped[str] = mapped_column(String(250), default="main")
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0)
    sync_state: Mapped[str] = mapped_column(String(20), default="ready")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"]),
        ForeignKeyConstraint(
            ["org_id", "installation_id"],
            ["github_installations.org_id", "github_installations.installation_id"],
        ),
        Index("ix_github_repositories_project", "org_id", "project_id"),
    )


class WebhookDelivery(Base):
    __tablename__ = "github_deliveries"
    delivery_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    installation_id: Mapped[int] = mapped_column(BigInteger)
    event: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_github_deliveries_org_received", "org_id", "received_at"),)
