"""Organization and collaboration routes. All writes authorize in their transaction."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from devhub.auth import require_user
from devhub.db import get_db, set_tenant
from devhub.models import (
    AuditEvent,
    Comment,
    Discussion,
    Membership,
    Organization,
    OutboxEvent,
    Project,
    ProjectMember,
    Task,
    User,
    utcnow,
    uuid_string,
)
from devhub.policy import (
    author_or_maintainer,
    effective_project_role,
    fail,
    organization_access,
    project_access,
    require_admin,
    validate_assignee,
)
from devhub.schemas import (
    CommentCreate,
    CommentOut,
    DiscussionCreate,
    DiscussionOut,
    DiscussionPatch,
    MemberCreate,
    MemberOut,
    MemberPatch,
    OrganizationCreate,
    OrganizationOut,
    Page,
    ProjectCreate,
    ProjectGrantCreate,
    ProjectGrantOut,
    ProjectOut,
    ProjectPatch,
    TaskCreate,
    TaskOut,
    TaskPatch,
    TaskStatus,
)

router = APIRouter(prefix="/api/v1/organizations", tags=["collaboration"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(require_user)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100000)]


def emit(
    db: Session, org_id: str, user: User, action: str, resource_id: str, details: dict | None = None
) -> None:
    event_id = uuid_string()
    db.add(
        AuditEvent(
            org_id=org_id, actor_id=user.id, action=action, resource_id=resource_id, details=details or {}
        )
    )
    db.add(
        OutboxEvent(
            id=event_id,
            org_id=org_id,
            kind="collaboration.changed",
            dedupe_key=event_id,
            payload={"version": 1, "org_id": org_id, "action": action, "resource_id": resource_id},
        )
    )


def flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        fail(409, "conflict", "A record with this identifier already exists or a relationship changed")


def page(db: Session, query, model, limit: int, offset: int) -> dict:
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items = list(db.scalars(query.order_by(model.created_at, model.id).limit(limit).offset(offset)))
    return {"items": items, "total": total}


def project_data(project: Project, role: str) -> dict:
    return {
        **{column.name: getattr(project, column.name) for column in Project.__table__.columns},
        "effective_role": role,
    }


def org_data(org: Organization, membership: Membership) -> dict:
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "created_at": org.created_at,
        "role": membership.role,
    }


def member_data(member: Membership, user: User) -> dict:
    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": member.role,
        "active": member.active,
        "created_at": member.created_at,
    }


def version_check(resource, version: int) -> None:
    if resource.version != version:
        fail(409, "version_conflict", "This record changed. Refresh before trying again")


def apply_patch(resource, payload) -> None:
    version_check(resource, payload.version)
    for name, value in payload.model_dump(mode="json", exclude_unset=True, exclude={"version"}).items():
        setattr(resource, name, value)
    resource.version += 1
    resource.updated_at = utcnow()


def content(db: Session, model, org_id: UUID, project_id: UUID, resource_id: UUID, lock: bool = False):
    query = select(model).where(
        model.org_id == str(org_id), model.project_id == str(project_id), model.id == str(resource_id)
    )
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        fail(404, "not_found", "Resource not found")
    return item


@router.get("", response_model=Page[OrganizationOut])
def organizations(db: DB, user: Actor, limit: Limit = 50, offset: Offset = 0):
    query = (
        select(Organization, Membership)
        .join(Membership, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id, Membership.active.is_(True))
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(Organization.created_at, Organization.id).limit(limit).offset(offset)
    ).all()
    return {"items": [org_data(org, membership) for org, membership in rows], "total": total}


@router.post("", response_model=OrganizationOut, status_code=201)
def create_organization(payload: OrganizationCreate, db: DB, user: Actor):
    org = Organization(**payload.model_dump(), created_by=user.id)
    db.add(org)
    flush(db)
    membership = Membership(org_id=org.id, user_id=user.id, role="owner")
    db.add(membership)
    set_tenant(db, org.id)
    emit(db, org.id, user, "organization.created", org.id)
    flush(db)
    return org_data(org, membership)


@router.get("/{org_id}", response_model=OrganizationOut)
def organization(org_id: UUID, db: DB, user: Actor):
    membership = organization_access(db, user, str(org_id))
    return org_data(db.get(Organization, str(org_id)), membership)


@router.get("/{org_id}/members", response_model=Page[MemberOut])
def members(org_id: UUID, db: DB, user: Actor, limit: Limit = 50, offset: Offset = 0):
    membership = organization_access(db, user, str(org_id))
    require_admin(membership)
    query = (
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.org_id == str(org_id), Membership.active.is_(True))
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(Membership.created_at, Membership.user_id).limit(limit).offset(offset)
    ).all()
    return {"items": [member_data(member, person) for member, person in rows], "total": total}


def check_member_change(
    db: Session, actor: Membership, target: Membership | None, new_role: str | None
) -> None:
    require_admin(actor)
    if actor.role != "owner" and (
        new_role in {"owner", "admin"} or (target is not None and target.role in {"owner", "admin"})
    ):
        fail(403, "forbidden", "Only an owner may manage owner or administrator roles")
    if target is not None and target.active and target.role == "owner" and new_role != "owner":
        owners = db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.org_id == target.org_id, Membership.active.is_(True), Membership.role == "owner"
            )
        )
        if owners <= 1:
            fail(409, "last_owner", "An organization must retain at least one active owner")


@router.post("/{org_id}/members", response_model=MemberOut, status_code=201)
def add_member(org_id: UUID, payload: MemberCreate, db: DB, user: Actor):
    actor = organization_access(db, user, str(org_id), lock=True)
    require_admin(actor)
    people = list(
        db.scalars(
            select(User)
            .where(func.lower(User.email) == payload.email.lower(), User.disabled.is_(False))
            .limit(2)
        )
    )
    if not people:
        fail(422, "unknown_member", "The user must sign in before being added; invitations are not enabled")
    if len(people) != 1:
        fail(
            409,
            "ambiguous_email",
            "This email belongs to multiple identities; administrator resolution is required",
        )
    person = people[0]
    target = db.get(Membership, (str(org_id), person.id))
    check_member_change(db, actor, target, payload.role)
    if target is not None and target.active:
        fail(409, "already_member", "This user is already an active member")
    if target is None:
        target = Membership(org_id=str(org_id), user_id=person.id, role=payload.role)
        db.add(target)
    else:
        target.role, target.active = payload.role, True
    emit(db, str(org_id), user, "member.added", person.id, {"role": payload.role})
    flush(db)
    return member_data(target, person)


@router.patch("/{org_id}/members/{user_id}", response_model=MemberOut)
def update_member(org_id: UUID, user_id: UUID, payload: MemberPatch, db: DB, user: Actor):
    actor = organization_access(db, user, str(org_id), lock=True)
    require_admin(actor)
    target = db.get(Membership, (str(org_id), str(user_id)))
    if target is None or not target.active:
        fail(404, "not_found", "Member not found")
    check_member_change(db, actor, target, payload.role)
    target.role = payload.role
    emit(db, str(org_id), user, "member.role_changed", str(user_id), {"role": payload.role})
    flush(db)
    return member_data(target, db.get(User, str(user_id)))


@router.delete("/{org_id}/members/{user_id}", status_code=204)
def remove_member(org_id: UUID, user_id: UUID, db: DB, user: Actor):
    actor = organization_access(db, user, str(org_id), lock=True)
    require_admin(actor)
    target = db.get(Membership, (str(org_id), str(user_id)))
    if target is None or not target.active:
        fail(404, "not_found", "Member not found")
    check_member_change(db, actor, target, None)
    target.active = False
    # Membership history remains for authorship; access grants never survive a
    # removal/reactivation cycle, and assignments cannot retain removed users.
    db.execute(
        delete(ProjectMember).where(
            ProjectMember.org_id == str(org_id), ProjectMember.user_id == str(user_id)
        )
    )
    db.execute(
        update(Task)
        .where(Task.org_id == str(org_id), Task.assignee_id == str(user_id))
        .values(assignee_id=None, version=Task.version + 1, updated_at=utcnow())
    )
    emit(db, str(org_id), user, "member.removed", str(user_id))
    flush(db)
    return Response(status_code=204)


@router.get("/{org_id}/projects", response_model=Page[ProjectOut])
def projects(org_id: UUID, db: DB, user: Actor, limit: Limit = 50, offset: Offset = 0):
    membership = organization_access(db, user, str(org_id))
    query = select(Project).where(Project.org_id == str(org_id))
    if membership.role not in {"owner", "admin"}:
        grant = exists(
            select(1).where(
                ProjectMember.org_id == Project.org_id,
                ProjectMember.project_id == Project.id,
                ProjectMember.user_id == user.id,
            )
        )
        query = query.where(or_(Project.visibility == "organization", grant))
    result = page(db, query, Project, limit, offset)
    result["items"] = [
        project_data(project, effective_project_role(db, membership, project)) for project in result["items"]
    ]
    return result


@router.post("/{org_id}/projects", response_model=ProjectOut, status_code=201)
def create_project(org_id: UUID, payload: ProjectCreate, db: DB, user: Actor):
    membership = organization_access(db, user, str(org_id))
    if membership.role == "viewer":
        fail(403, "forbidden", "Viewers cannot create projects")
    project = Project(org_id=str(org_id), created_by=user.id, **payload.model_dump())
    db.add(project)
    flush(db)
    db.add(ProjectMember(org_id=str(org_id), project_id=project.id, user_id=user.id, role="maintainer"))
    emit(db, str(org_id), user, "project.created", project.id)
    flush(db)
    return project_data(project, "maintainer")


@router.get("/{org_id}/projects/{project_id}", response_model=ProjectOut)
def project_detail(org_id: UUID, project_id: UUID, db: DB, user: Actor):
    project, role = project_access(db, user, str(org_id), str(project_id))
    return project_data(project, role)


@router.patch("/{org_id}/projects/{project_id}", response_model=ProjectOut)
def update_project(org_id: UUID, project_id: UUID, payload: ProjectPatch, db: DB, user: Actor):
    project, role = project_access(db, user, str(org_id), str(project_id), maintain=True)
    apply_patch(project, payload)
    if payload.visibility == "private":
        # Existing assignments must not point at members losing visibility.
        tasks = db.scalars(
            select(Task).where(
                Task.org_id == str(org_id), Task.project_id == project.id, Task.assignee_id.is_not(None)
            )
        )
        for task in tasks:
            member = db.get(Membership, (str(org_id), task.assignee_id))
            if member is None or effective_project_role(db, member, project) is None:
                task.assignee_id = None
                task.version += 1
                task.updated_at = utcnow()
    emit(
        db,
        str(org_id),
        user,
        "project.updated",
        project.id,
        {"fields": sorted(payload.model_fields_set - {"version"})},
    )
    flush(db)
    return project_data(project, role)


@router.get("/{org_id}/projects/{project_id}/members", response_model=Page[ProjectGrantOut])
def project_members(
    org_id: UUID, project_id: UUID, db: DB, user: Actor, limit: Limit = 50, offset: Offset = 0
):
    project_access(db, user, str(org_id), str(project_id), maintain=True)
    query = select(ProjectMember).where(
        ProjectMember.org_id == str(org_id), ProjectMember.project_id == str(project_id)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.add_columns(User)
        .join(User, User.id == ProjectMember.user_id)
        .order_by(ProjectMember.created_at, ProjectMember.user_id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [
            {
                "user_id": grant.user_id,
                "role": grant.role,
                "created_at": grant.created_at,
                "email": person.email,
                "display_name": person.display_name,
            }
            for grant, person in rows
        ],
        "total": total,
    }


@router.post("/{org_id}/projects/{project_id}/members", response_model=ProjectGrantOut, status_code=201)
def grant_project_member(org_id: UUID, project_id: UUID, payload: ProjectGrantCreate, db: DB, user: Actor):
    project, _ = project_access(db, user, str(org_id), str(project_id), maintain=True, lock=True)
    if payload.email:
        people = list(
            db.scalars(
                select(User)
                .join(Membership, Membership.user_id == User.id)
                .where(
                    Membership.org_id == str(org_id),
                    Membership.active.is_(True),
                    User.disabled.is_(False),
                    func.lower(User.email) == payload.email.lower(),
                )
                .limit(2)
            )
        )
        if len(people) != 1:
            fail(422, "invalid_member", "An unambiguous active organization member is required")
        payload.user_id = UUID(people[0].id)
    member = db.get(Membership, (str(org_id), str(payload.user_id)))
    person = db.get(User, str(payload.user_id))
    if member is None or not member.active or person is None or person.disabled:
        fail(422, "invalid_member", "Project grants require active organization membership")
    grant = db.get(ProjectMember, (str(org_id), str(project_id), str(payload.user_id)))
    if grant is None:
        grant = ProjectMember(
            org_id=str(org_id), project_id=project.id, user_id=str(payload.user_id), role=payload.role
        )
        db.add(grant)
    else:
        grant.role = payload.role
    emit(
        db,
        str(org_id),
        user,
        "project.grant_changed",
        project.id,
        {"user_id": str(payload.user_id), "role": payload.role},
    )
    flush(db)
    return grant


@router.delete("/{org_id}/projects/{project_id}/members/{user_id}", status_code=204)
def revoke_project_member(org_id: UUID, project_id: UUID, user_id: UUID, db: DB, user: Actor):
    project, _ = project_access(db, user, str(org_id), str(project_id), maintain=True, lock=True)
    grant = db.get(ProjectMember, (str(org_id), str(project_id), str(user_id)))
    if grant is None:
        fail(404, "not_found", "Project grant not found")
    db.delete(grant)
    db.flush()
    member = db.get(Membership, (str(org_id), str(user_id)))
    if member is None or effective_project_role(db, member, project) is None:
        db.execute(
            update(Task)
            .where(
                Task.org_id == str(org_id), Task.project_id == project.id, Task.assignee_id == str(user_id)
            )
            .values(assignee_id=None, version=Task.version + 1, updated_at=utcnow())
        )
    emit(db, str(org_id), user, "project.grant_removed", project.id, {"user_id": str(user_id)})
    flush(db)
    return Response(status_code=204)


@router.get("/{org_id}/projects/{project_id}/tasks", response_model=Page[TaskOut])
def tasks(
    org_id: UUID,
    project_id: UUID,
    db: DB,
    user: Actor,
    limit: Limit = 50,
    offset: Offset = 0,
    status: TaskStatus | None = None,
    assignee_id: UUID | None = None,
):
    project_access(db, user, str(org_id), str(project_id))
    query = select(Task).where(Task.org_id == str(org_id), Task.project_id == str(project_id))
    if status is not None:
        query = query.where(Task.status == status)
    if assignee_id is not None:
        query = query.where(Task.assignee_id == str(assignee_id))
    return page(db, query, Task, limit, offset)


@router.post("/{org_id}/projects/{project_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(org_id: UUID, project_id: UUID, payload: TaskCreate, db: DB, user: Actor):
    project, _ = project_access(db, user, str(org_id), str(project_id), write=True)
    values = payload.model_dump(mode="json")
    validate_assignee(db, project, values["assignee_id"])
    task = Task(org_id=str(org_id), project_id=str(project_id), created_by=user.id, **values)
    db.add(task)
    flush(db)
    emit(db, str(org_id), user, "task.created", task.id)
    flush(db)
    return task


@router.patch("/{org_id}/projects/{project_id}/tasks/{task_id}", response_model=TaskOut)
def update_task(org_id: UUID, project_id: UUID, task_id: UUID, payload: TaskPatch, db: DB, user: Actor):
    project, _ = project_access(db, user, str(org_id), str(project_id), write=True)
    task = content(db, Task, org_id, project_id, task_id, lock=True)
    if "assignee_id" in payload.model_fields_set:
        validate_assignee(db, project, str(payload.assignee_id) if payload.assignee_id else None)
    apply_patch(task, payload)
    emit(
        db,
        str(org_id),
        user,
        "task.updated",
        task.id,
        {"fields": sorted(payload.model_fields_set - {"version"})},
    )
    flush(db)
    return task


@router.delete("/{org_id}/projects/{project_id}/tasks/{task_id}", status_code=204)
def delete_task(org_id: UUID, project_id: UUID, task_id: UUID, db: DB, user: Actor):
    _, role = project_access(db, user, str(org_id), str(project_id), write=True)
    task = content(db, Task, org_id, project_id, task_id, lock=True)
    author_or_maintainer(user, task.created_by, role)
    db.delete(task)
    emit(db, str(org_id), user, "task.deleted", str(task_id))
    flush(db)
    return Response(status_code=204)


@router.get("/{org_id}/projects/{project_id}/discussions", response_model=Page[DiscussionOut])
def discussions(org_id: UUID, project_id: UUID, db: DB, user: Actor, limit: Limit = 50, offset: Offset = 0):
    project_access(db, user, str(org_id), str(project_id))
    return page(
        db,
        select(Discussion).where(Discussion.org_id == str(org_id), Discussion.project_id == str(project_id)),
        Discussion,
        limit,
        offset,
    )


@router.post("/{org_id}/projects/{project_id}/discussions", response_model=DiscussionOut, status_code=201)
def create_discussion(org_id: UUID, project_id: UUID, payload: DiscussionCreate, db: DB, user: Actor):
    project_access(db, user, str(org_id), str(project_id), write=True)
    discussion = Discussion(
        org_id=str(org_id), project_id=str(project_id), created_by=user.id, **payload.model_dump()
    )
    db.add(discussion)
    flush(db)
    emit(db, str(org_id), user, "discussion.created", discussion.id)
    flush(db)
    return discussion


@router.get("/{org_id}/projects/{project_id}/discussions/{discussion_id}", response_model=DiscussionOut)
def discussion_detail(org_id: UUID, project_id: UUID, discussion_id: UUID, db: DB, user: Actor):
    project_access(db, user, str(org_id), str(project_id))
    return content(db, Discussion, org_id, project_id, discussion_id)


@router.patch("/{org_id}/projects/{project_id}/discussions/{discussion_id}", response_model=DiscussionOut)
def update_discussion(
    org_id: UUID, project_id: UUID, discussion_id: UUID, payload: DiscussionPatch, db: DB, user: Actor
):
    _, role = project_access(db, user, str(org_id), str(project_id), write=True)
    discussion = content(db, Discussion, org_id, project_id, discussion_id, lock=True)
    author_or_maintainer(user, discussion.created_by, role)
    apply_patch(discussion, payload)
    emit(db, str(org_id), user, "discussion.updated", discussion.id)
    flush(db)
    return discussion


@router.delete("/{org_id}/projects/{project_id}/discussions/{discussion_id}", status_code=204)
def delete_discussion(org_id: UUID, project_id: UUID, discussion_id: UUID, db: DB, user: Actor):
    _, role = project_access(db, user, str(org_id), str(project_id), write=True)
    discussion = content(db, Discussion, org_id, project_id, discussion_id, lock=True)
    author_or_maintainer(user, discussion.created_by, role)
    db.delete(discussion)
    emit(db, str(org_id), user, "discussion.deleted", str(discussion_id))
    flush(db)
    return Response(status_code=204)


@router.get(
    "/{org_id}/projects/{project_id}/discussions/{discussion_id}/comments", response_model=Page[CommentOut]
)
def comments(
    org_id: UUID,
    project_id: UUID,
    discussion_id: UUID,
    db: DB,
    user: Actor,
    limit: Limit = 50,
    offset: Offset = 0,
):
    project_access(db, user, str(org_id), str(project_id))
    content(db, Discussion, org_id, project_id, discussion_id)
    return page(
        db,
        select(Comment).where(
            Comment.org_id == str(org_id),
            Comment.project_id == str(project_id),
            Comment.discussion_id == str(discussion_id),
        ),
        Comment,
        limit,
        offset,
    )


@router.post(
    "/{org_id}/projects/{project_id}/discussions/{discussion_id}/comments",
    response_model=CommentOut,
    status_code=201,
)
def create_comment(
    org_id: UUID, project_id: UUID, discussion_id: UUID, payload: CommentCreate, db: DB, user: Actor
):
    project_access(db, user, str(org_id), str(project_id), write=True)
    content(db, Discussion, org_id, project_id, discussion_id)
    comment = Comment(
        org_id=str(org_id),
        project_id=str(project_id),
        discussion_id=str(discussion_id),
        author_id=user.id,
        **payload.model_dump(),
    )
    db.add(comment)
    flush(db)
    emit(db, str(org_id), user, "comment.created", comment.id)
    flush(db)
    return comment


@router.delete(
    "/{org_id}/projects/{project_id}/discussions/{discussion_id}/comments/{comment_id}", status_code=204
)
def delete_comment(
    org_id: UUID, project_id: UUID, discussion_id: UUID, comment_id: UUID, db: DB, user: Actor
):
    _, role = project_access(db, user, str(org_id), str(project_id), write=True)
    content(db, Discussion, org_id, project_id, discussion_id)
    comment = content(db, Comment, org_id, project_id, comment_id, lock=True)
    if comment.discussion_id != str(discussion_id):
        fail(404, "not_found", "Comment not found")
    author_or_maintainer(user, comment.author_id, role)
    db.delete(comment)
    emit(db, str(org_id), user, "comment.deleted", str(comment_id))
    flush(db)
    return Response(status_code=204)
