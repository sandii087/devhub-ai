"""Explicit request/response contracts, including bounded untrusted content."""

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

OrgRole = Literal["owner", "admin", "member", "viewer"]
ProjectRole = Literal["maintainer", "contributor", "viewer"]
Visibility = Literal["organization", "private"]
TaskStatus = Literal["todo", "in_progress", "done"]
Priority = Literal["low", "medium", "high", "urgent"]
T = TypeVar("T")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(Output, Generic[T]):
    items: list[T]
    total: int


class OrganizationCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OrganizationOut(Output):
    id: str
    name: str
    slug: str
    role: OrgRole
    created_at: datetime


class MemberCreate(Input):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: OrgRole = "member"


class MemberPatch(Input):
    role: OrgRole


class MemberOut(Output):
    user_id: str
    email: str
    display_name: str
    role: OrgRole
    active: bool
    created_at: datetime


class ProjectCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(default="", max_length=20000)
    visibility: Visibility = "organization"


class VersionPatch(Input):
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def reject_null_fields(self):
        for name in self.model_fields_set:
            if name != "assignee_id" and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if self.model_fields_set == {"version"}:
            raise ValueError("Provide at least one field to update")
        return self


class ProjectPatch(VersionPatch):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=20000)
    visibility: Visibility | None = None
    archived: bool | None = None


class ProjectOut(Output):
    id: str
    org_id: str
    name: str
    slug: str
    description: str
    visibility: Visibility
    archived: bool
    version: int
    effective_role: ProjectRole
    created_at: datetime
    updated_at: datetime


class ProjectGrantCreate(Input):
    user_id: UUID | None = None
    email: str | None = Field(default=None, max_length=320)
    role: ProjectRole

    @model_validator(mode="after")
    def one_identity(self):
        if bool(self.user_id) == bool(self.email):
            raise ValueError("Provide either user_id or email")
        return self


class ProjectGrantOut(Output):
    user_id: str
    role: ProjectRole
    created_at: datetime
    email: str = ""
    display_name: str = ""


class TaskCreate(Input):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    status: TaskStatus = "todo"
    priority: Priority = "medium"
    assignee_id: UUID | None = None


class TaskPatch(VersionPatch):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    status: TaskStatus | None = None
    priority: Priority | None = None
    assignee_id: UUID | None = None


class TaskOut(Output):
    id: str
    org_id: str
    project_id: str
    title: str
    description: str
    status: TaskStatus
    priority: Priority
    created_by: str
    assignee_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class DiscussionCreate(Input):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)


class DiscussionPatch(VersionPatch):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=20000)


class DiscussionOut(Output):
    id: str
    org_id: str
    project_id: str
    title: str
    body: str
    created_by: str
    version: int
    created_at: datetime
    updated_at: datetime


class CommentCreate(Input):
    body: str = Field(min_length=1, max_length=10000)


class CommentOut(Output):
    id: str
    org_id: str
    project_id: str
    discussion_id: str
    body: str
    author_id: str
    created_at: datetime
