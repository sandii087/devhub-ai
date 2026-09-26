# Requirements and phased implementation

## Confirmed requirements

The user selected a developer collaboration hub with organizations, projects, tasks, discussions, and GitHub integration, and authorized implementation from scratch after architecture analysis. No customer-churn product code or data may be reused.

## Proposed behavior

| ID | Capability | Acceptance condition |
| --- | --- | --- |
| R1 | Sign in and maintain session | GitHub OAuth validates state, browser binding, expiry, PKCE and primary verified email; logout revokes the session |
| R2 | Organizations and membership | Creator becomes owner; role changes are authorized; the last owner cannot be removed |
| R3 | Projects | Organization-visible and private projects; private project lists never reveal unauthorized names/counts |
| R4 | Tasks | Create, assign, filter, update status and edit with conflict detection |
| R5 | Discussions | Create project threads and add comments with author/moderator rules |
| R6 | GitHub | Administrator connects a verified installation/repository; signed deliveries update read-only metadata without duplicate effects |
| R7 | Security | Cross-organization resource substitution, CSRF, session replay after logout, and privilege escalation tests fail safely |
| R8 | Operations | Reproducible builds, migration path, health/readiness, deployment templates, documented restore/rollback |

Organization roles: owner, admin, member, viewer. Owner/admin may manage all projects; members can contribute to organization-visible projects; viewers remain read-only. Private projects require an explicit grant for ordinary members. Project roles: maintainer, contributor, viewer. Only owners manage owner/admin roles or organization deletion. These choices are proposed product policy and implemented consistently rather than inferred from GitHub permissions.

## Milestones

| Milestone | Deliverables | Exit gate |
| --- | --- | --- |
| M0 — foundation and documentation | Independent app layout, architecture/schema/API/security/operations docs, pinned dependencies, environment contract | No import from old product; boundaries and startup steps reviewable |
| M1 — identity and tenancy | PostgreSQL models/migrations, sessions, GitHub OAuth, organizations, role checks, tenant isolation | Auth and cross-tenant tests; production rejects development auth |
| M2 — projects and tasks | Responsive UI, project visibility/grants, task CRUD and assignment, optimistic concurrency | Full browser workflow plus role/foreign-ID/conflict tests |
| M3 — discussions | Threads, comments, author/moderator controls | End-to-end creation and authorization tests |
| M4 — GitHub and asynchronous work | Signed webhook receipts, installation/repo verification, idempotent processing, retry worker | Forged/duplicate/out-of-order delivery tests; provider outage isolation |
| M5 — release hardening | CI, containers, migration/rollback/runbooks, security review and dependency checks | All automated checks; documented operator launch gates |

Dependencies: M1 precedes all collaboration; M2 precedes discussions and repository mapping; M4 depends on stable organization policies; M5 validates the whole system. UI work may proceed against the agreed API contract after M0. Production secrets and accounts do not block local tests, but live GitHub OAuth/GitHub App verification is a release gate.

## Release gates requiring an operator environment

Choose cloud region and budget, register GitHub OAuth and GitHub repository-integration applications with exact callback URLs, provision least-privilege database roles and secrets, validate TLS/ingress rules, exercise backup restore and failover, load test the planning envelope, and assign alert/on-call ownership. Do not describe template files or passing local tests as a deployed production service.

## Change policy

Milestone results and limitations go in `progress.md`. Expand schema before deploying readers/writers; backfill separately; remove old fields only after the old release is retired. A failed gate is recorded and fixed before claiming its milestone is verified.
