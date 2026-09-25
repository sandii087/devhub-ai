"""Resource policies shared by HTTP modules; never authorize from client roles."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from devhub.db import set_tenant
from devhub.models import Membership, Organization, Project, ProjectMember, User


def fail(status: int, code: str, detail: str) -> None:
    raise HTTPException(status, detail={"code": code, "detail": detail})


def organization_access(db: Session, user: User, org_id: str, lock: bool = False) -> Membership:
    org_id = str(org_id)
    # Readers hold a shared organization lock through the transaction. Role and
    # grant mutations acquire its exclusive counterpart before checking policy.
    org = db.scalar(select(Organization).where(Organization.id == org_id).with_for_update(read=not lock))
    membership = db.get(Membership, (org_id, user.id)) if org is not None else None
    if user.disabled or membership is None or not membership.active:
        fail(404, "not_found", "Organization not found")
    set_tenant(db, org_id)
    return membership


def require_admin(membership: Membership) -> None:
    if membership.role not in {"owner", "admin"}:
        fail(403, "forbidden", "Organization administrator permission required")


def effective_project_role(db: Session, membership: Membership, project: Project) -> str | None:
    if not membership.active:
        return None
    if membership.role in {"owner", "admin"}:
        return "maintainer"
    grant = db.get(ProjectMember, (membership.org_id, project.id, membership.user_id))
    if project.visibility == "private" and grant is None:
        return None
    if membership.role == "viewer":
        return "viewer"
    if grant is not None:
        return grant.role
    return "contributor"


def project_access(
    db: Session,
    user: User,
    org_id: str,
    project_id: str,
    write: bool = False,
    maintain: bool = False,
    lock: bool = False,
) -> tuple[Project, str]:
    membership = organization_access(db, user, str(org_id), lock=lock)
    query = select(Project).where(Project.org_id == str(org_id), Project.id == str(project_id))
    if write or maintain:
        query = query.with_for_update()
    project = db.scalar(query)
    role = effective_project_role(db, membership, project) if project is not None else None
    if role is None:
        fail(404, "not_found", "Project not found")
    if maintain and role != "maintainer":
        fail(403, "forbidden", "Project maintainer permission required")
    if write and role == "viewer":
        fail(403, "forbidden", "Project contribution permission required")
    if write and project.archived:
        fail(409, "project_archived", "Restore this project before changing its content")
    return project, role


def author_or_maintainer(user: User, author_id: str, role: str) -> None:
    if user.id != author_id and role != "maintainer":
        fail(403, "forbidden", "Only the author or a project maintainer may perform this action")


def validate_assignee(db: Session, project: Project, assignee_id: str | None) -> None:
    if assignee_id is None:
        return
    membership = db.get(Membership, (project.org_id, assignee_id))
    user = db.get(User, assignee_id)
    if (
        membership is None
        or not membership.active
        or user is None
        or user.disabled
        or effective_project_role(db, membership, project) is None
    ):
        fail(422, "invalid_assignee", "Assignee must be an active member with access to this project")
