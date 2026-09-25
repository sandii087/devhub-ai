from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from devhub.db import set_tenant
from devhub.models import AuditEvent, Project


def test_tasks_conflict_and_audit(workspace, database):
    owner, org, project = workspace
    path = f"{org}/projects/{project['id']}/tasks"
    created = owner.post(path, json={"title": "Ship API", "assignee_id": owner.user_id})
    assert created.status_code == 201, created.text
    task = created.json()
    assert (
        owner.patch(path + "/" + task["id"], json={"version": 1, "status": "in_progress"}).json()["version"]
        == 2
    )
    assert owner.patch(path + "/" + task["id"], json={"version": 1, "status": "done"}).status_code == 409
    assert owner.get(path + "?status=in_progress").json()["total"] == 1
    with database() as db:
        set_tenant(db, project["org_id"])
        assert len(db.scalars(select(AuditEvent)).all()) >= 4


def test_private_project_and_cross_tenant_paths(workspace, clients):
    owner, org, project = workspace
    other = clients("other@example.com")
    assert other.get(org + "/projects").status_code == 404
    owner.post(org + "/members", json={"email": "other@example.com", "role": "member"})
    private = owner.post(
        org + "/projects", json={"name": "Secret", "slug": "secret", "visibility": "private"}
    ).json()
    path = org + "/projects/" + private["id"]
    assert other.get(path).status_code == 404
    assert other.get(org + "/projects").json()["total"] == 1
    assert (
        owner.post(path + "/members", json={"user_id": other.user_id, "role": "contributor"}).status_code
        == 201
    )
    assert other.get(path).status_code == 200
    org2 = other.post("/api/v1/organizations", json={"name": "Other", "slug": "other"}).json()
    assert other.get(f"/api/v1/organizations/{org2['id']}/projects/{project['id']}").status_code == 404


def test_viewer_cannot_escalate_with_project_grant(workspace, clients):
    owner, org, project = workspace
    viewer = clients("viewer@example.com")
    owner.post(org + "/members", json={"email": "viewer@example.com", "role": "viewer"})
    path = org + "/projects/" + project["id"]
    owner.post(path + "/members", json={"user_id": viewer.user_id, "role": "maintainer"})
    assert viewer.get(path).json()["effective_role"] == "viewer"
    assert viewer.post(path + "/tasks", json={"title": "Escalate"}).status_code == 403
    assert viewer.post(org + "/projects", json={"name": "No", "slug": "no"}).status_code == 403


def test_last_owner_and_admin_role_ceiling(workspace, clients):
    owner, org, project = workspace
    assert owner.delete(org + "/members/" + owner.user_id).status_code == 409
    admin = clients("admin@example.com")
    owner.post(org + "/members", json={"email": "admin@example.com", "role": "admin"})
    assert admin.patch(org + "/members/" + admin.user_id, json={"role": "owner"}).status_code == 403
    assert admin.delete(org + "/members/" + owner.user_id).status_code == 403


def test_removal_revokes_access_and_grants(workspace, clients):
    owner, org, project = workspace
    member = clients("member@example.com")
    owner.post(org + "/members", json={"email": "member@example.com", "role": "member"})
    path = org + "/projects/" + project["id"]
    owner.post(path + "/members", json={"user_id": member.user_id, "role": "maintainer"})
    assert owner.delete(org + "/members/" + member.user_id).status_code == 204
    assert member.get(path).status_code == 404
    owner.post(org + "/members", json={"email": "member@example.com", "role": "member"})
    assert member.get(path).json()["effective_role"] == "contributor"


def test_discussion_comments_and_author_permissions(workspace, clients):
    owner, org, project = workspace
    member = clients("member@example.com")
    owner.post(org + "/members", json={"email": "member@example.com", "role": "member"})
    path = org + "/projects/" + project["id"] + "/discussions"
    discussion = owner.post(path, json={"title": "Architecture", "body": "Use PostgreSQL"}).json()
    thread = path + "/" + discussion["id"]
    comment = member.post(thread + "/comments", json={"body": "Agreed"})
    assert comment.status_code == 201
    assert member.patch(thread, json={"version": 1, "body": "Hijacked"}).status_code == 403
    assert member.delete(thread + "/comments/" + comment.json()["id"]).status_code == 204
    assert owner.get(thread + "/comments").json()["total"] == 0


def test_foreign_assignee_and_invalid_fields(workspace):
    owner, org, project = workspace
    path = org + "/projects/" + project["id"] + "/tasks"
    assert owner.post(path, json={"title": "Task", "assignee_id": str(uuid4())}).status_code == 422
    assert owner.post(path, json={"title": "Task", "org_id": str(uuid4())}).status_code == 422
    assert owner.get(path + "?limit=1000").status_code == 422


def test_database_rls_default_deny_and_tenant_scope(workspace, database):
    _, _, project = workspace
    with database() as db:
        db.execute(text("SELECT set_config('devhub.org_id', '', true)"))
        assert db.scalars(select(Project)).all() == []
        set_tenant(db, str(uuid4()))
        assert db.scalars(select(Project)).all() == []
        set_tenant(db, project["org_id"])
        assert len(db.scalars(select(Project)).all()) == 1
        with pytest.raises(DBAPIError):
            with db.begin_nested():
                db.execute(text("UPDATE projects SET org_id=:other"), {"other": str(uuid4())})
        with pytest.raises(DBAPIError):
            with db.begin_nested():
                db.execute(text("DELETE FROM audit_events"))


def test_archived_project_rejects_content_writes(workspace):
    owner, org, project = workspace
    path = org + "/projects/" + project["id"]
    assert owner.patch(path, json={"version": 1, "archived": True}).status_code == 200
    assert owner.post(path + "/tasks", json={"title": "No"}).status_code == 409
