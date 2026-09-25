-- Frozen initial schema; do not regenerate after first release.


CREATE TABLE oidc_flows (
	state_hash VARCHAR(64) NOT NULL,
	nonce VARCHAR(128) NOT NULL,
	code_verifier VARCHAR(128) NOT NULL,
	browser_hash VARCHAR(64) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (state_hash)
)

;

CREATE INDEX ix_oidc_flows_expires_at ON oidc_flows (expires_at);


CREATE TABLE users (
	id UUID NOT NULL,
	email VARCHAR(320) NOT NULL,
	display_name VARCHAR(100) NOT NULL,
	disabled BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_users_email ON users (email);


CREATE TABLE identities (
	id UUID NOT NULL,
	issuer TEXT NOT NULL,
	subject TEXT NOT NULL,
	user_id UUID NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_identity_issuer_subject UNIQUE (issuer, subject),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE INDEX ix_identities_user_id ON identities (user_id);


CREATE TABLE organizations (
	id UUID NOT NULL,
	name VARCHAR(100) NOT NULL,
	slug VARCHAR(80) NOT NULL,
	created_by UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (slug),
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;


CREATE TABLE sessions (
	token_hash VARCHAR(64) NOT NULL,
	user_id UUID NOT NULL,
	csrf_token VARCHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	revoked_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE INDEX ix_sessions_expires_at ON sessions (expires_at);

CREATE INDEX ix_sessions_user_id ON sessions (user_id);


CREATE TABLE audit_events (
	id UUID NOT NULL,
	org_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	action VARCHAR(80) NOT NULL,
	resource_id VARCHAR(100) NOT NULL,
	details JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(org_id) REFERENCES organizations (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;

CREATE INDEX ix_audit_org_created ON audit_events (org_id, created_at);


CREATE TABLE github_deliveries (
	delivery_id VARCHAR(100) NOT NULL,
	org_id UUID NOT NULL,
	installation_id BIGINT NOT NULL,
	event VARCHAR(80) NOT NULL,
	payload JSONB NOT NULL,
	received_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (delivery_id),
	FOREIGN KEY(org_id) REFERENCES organizations (id)
)

;

CREATE INDEX ix_github_deliveries_org_received ON github_deliveries (org_id, received_at);


CREATE TABLE github_installations (
	installation_id BIGSERIAL NOT NULL,
	org_id UUID NOT NULL,
	account_login VARCHAR(100) NOT NULL,
	enabled BOOLEAN NOT NULL,
	verified BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (installation_id),
	CONSTRAINT uq_installation_org_id UNIQUE (org_id, installation_id),
	FOREIGN KEY(org_id) REFERENCES organizations (id)
)

;


CREATE TABLE memberships (
	org_id UUID NOT NULL,
	user_id UUID NOT NULL,
	role VARCHAR(16) NOT NULL,
	active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (org_id, user_id),
	CONSTRAINT membership_role CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
	FOREIGN KEY(org_id) REFERENCES organizations (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE INDEX ix_memberships_user_active ON memberships (user_id, active);


CREATE TABLE outbox_events (
	id UUID NOT NULL,
	org_id UUID NOT NULL,
	kind VARCHAR(100) NOT NULL,
	payload JSONB NOT NULL,
	dedupe_key VARCHAR(200) NOT NULL,
	state VARCHAR(16) NOT NULL,
	attempts INTEGER NOT NULL,
	next_retry_at TIMESTAMP WITH TIME ZONE NOT NULL,
	lease_owner VARCHAR(100),
	lease_expires_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT outbox_state CHECK (state IN ('pending', 'processing', 'done', 'dead')),
	FOREIGN KEY(org_id) REFERENCES organizations (id),
	UNIQUE (dedupe_key)
)

;

CREATE INDEX ix_outbox_pending ON outbox_events (state, next_retry_at);


CREATE TABLE projects (
	id UUID NOT NULL,
	org_id UUID NOT NULL,
	name VARCHAR(100) NOT NULL,
	slug VARCHAR(80) NOT NULL,
	description TEXT NOT NULL,
	visibility VARCHAR(16) NOT NULL,
	archived BOOLEAN NOT NULL,
	created_by UUID NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_projects_org_id UNIQUE (org_id, id),
	CONSTRAINT uq_projects_org_slug UNIQUE (org_id, slug),
	FOREIGN KEY(org_id, created_by) REFERENCES memberships (org_id, user_id),
	CONSTRAINT project_visibility CHECK (visibility IN ('organization', 'private')),
	CONSTRAINT project_version CHECK (version > 0),
	FOREIGN KEY(org_id) REFERENCES organizations (id)
)

;

CREATE INDEX ix_projects_org_created ON projects (org_id, created_at, id);


CREATE TABLE discussions (
	id UUID NOT NULL,
	org_id UUID NOT NULL,
	project_id UUID NOT NULL,
	title VARCHAR(200) NOT NULL,
	body TEXT NOT NULL,
	created_by UUID NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_discussions_org_project_id UNIQUE (org_id, project_id, id),
	FOREIGN KEY(org_id, project_id) REFERENCES projects (org_id, id),
	FOREIGN KEY(org_id, created_by) REFERENCES memberships (org_id, user_id),
	CONSTRAINT discussion_version CHECK (version > 0)
)

;

CREATE INDEX ix_discussions_project_created ON discussions (org_id, project_id, created_at, id);


CREATE TABLE github_repositories (
	id UUID NOT NULL,
	org_id UUID NOT NULL,
	project_id UUID NOT NULL,
	installation_id BIGINT NOT NULL,
	repository_id BIGINT NOT NULL,
	full_name VARCHAR(250) NOT NULL,
	html_url VARCHAR(500) NOT NULL,
	default_branch VARCHAR(250) NOT NULL,
	open_issues_count INTEGER NOT NULL,
	sync_state VARCHAR(20) NOT NULL,
	last_synced_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(org_id, project_id) REFERENCES projects (org_id, id),
	FOREIGN KEY(org_id, installation_id) REFERENCES github_installations (org_id, installation_id),
	UNIQUE (repository_id)
)

;

CREATE INDEX ix_github_repositories_project ON github_repositories (org_id, project_id);


CREATE TABLE project_members (
	org_id UUID NOT NULL,
	project_id UUID NOT NULL,
	user_id UUID NOT NULL,
	role VARCHAR(16) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (org_id, project_id, user_id),
	FOREIGN KEY(org_id, project_id) REFERENCES projects (org_id, id),
	FOREIGN KEY(org_id, user_id) REFERENCES memberships (org_id, user_id),
	CONSTRAINT project_member_role CHECK (role IN ('maintainer', 'contributor', 'viewer'))
)

;


CREATE TABLE tasks (
	id UUID NOT NULL,
	org_id UUID NOT NULL,
	project_id UUID NOT NULL,
	title VARCHAR(200) NOT NULL,
	description TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	priority VARCHAR(16) NOT NULL,
	created_by UUID NOT NULL,
	assignee_id UUID,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(org_id, project_id) REFERENCES projects (org_id, id),
	FOREIGN KEY(org_id, created_by) REFERENCES memberships (org_id, user_id),
	FOREIGN KEY(org_id, assignee_id) REFERENCES memberships (org_id, user_id),
	CONSTRAINT task_status CHECK (status IN ('todo', 'in_progress', 'done')),
	CONSTRAINT task_priority CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
	CONSTRAINT task_version CHECK (version > 0)
)

;

CREATE INDEX ix_tasks_assignee ON tasks (org_id, assignee_id);

CREATE INDEX ix_tasks_project_status_created ON tasks (org_id, project_id, status, created_at, id);


CREATE TABLE comments (
	id UUID NOT NULL,
	org_id UUID NOT NULL,
	project_id UUID NOT NULL,
	discussion_id UUID NOT NULL,
	body TEXT NOT NULL,
	author_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(org_id, project_id, discussion_id) REFERENCES discussions (org_id, project_id, id) ON DELETE CASCADE,
	FOREIGN KEY(org_id, author_id) REFERENCES memberships (org_id, user_id)
)

;

CREATE INDEX ix_comments_discussion_created ON comments (org_id, project_id, discussion_id, created_at, id);

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

ALTER TABLE projects FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON projects USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);

ALTER TABLE project_members ENABLE ROW LEVEL SECURITY;

ALTER TABLE project_members FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON project_members USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

ALTER TABLE tasks FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON tasks USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);

ALTER TABLE discussions ENABLE ROW LEVEL SECURITY;

ALTER TABLE discussions FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON discussions USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);

ALTER TABLE comments ENABLE ROW LEVEL SECURITY;

ALTER TABLE comments FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON comments USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON audit_events USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);

ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON outbox_events USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);

ALTER TABLE github_repositories ENABLE ROW LEVEL SECURITY;

ALTER TABLE github_repositories FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON github_repositories USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);

ALTER TABLE github_deliveries ENABLE ROW LEVEL SECURITY;

ALTER TABLE github_deliveries FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON github_deliveries USING (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid) WITH CHECK (org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid);
