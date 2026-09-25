# Implementation progress

Local implementation completed on 2026-09-25. This is a tested application baseline, not a certification that production infrastructure or external accounts are ready.

| Milestone | Implemented and verified locally |
| --- | --- |
| M0 — foundation | Independent Python/React project, locked dependencies, architecture, schema/API contracts and runbooks |
| M1 — identity and tenancy | OIDC/PKCE session flow, explicit local login, CSRF, revocation, organization roles, private-project grants, PostgreSQL RLS and tenant foreign keys |
| M2 — projects/tasks | Responsive workspace, project creation/access, task board, assignment, priorities/status, optimistic version conflicts and transactional audit/outbox |
| M3 — discussions | Discussions and replies with author/moderator authorization and tenant-scoped access |
| M4 — GitHub | Operator-bound installations, read-only repository metadata, HMAC webhooks, durable deduplication, leased jobs/retries and reconciliation; provider mocked in tests |
| M5 — AI | Explicit project opt-in, read-only drafts, context disclosure, per-user/organization quotas, request idempotency and provider contract tests |
| M6 — delivery | Dockerfiles/Compose, separate runtime roles, production configuration guards, CI and manually gated release workflow; Docker execution remains a launch gate |

## Verification evidence

- 50 backend tests using real PostgreSQL, including auth/CSRF, role ceilings, cross-tenant/private-project denial, RLS, last-owner protection, task conflicts, author permissions, webhook replay, worker retry, AI consent/quotas/idempotency, production configuration and chunked request size limits.
- Five frontend component/transport tests; strict TypeScript production build.
- Two Playwright journeys, desktop and mobile: login, create organization/project/task, change status, discussion/reply, disabled AI state, responsive overflow check and logout.
- Alembic upgrades and metadata/schema drift check; Ruff formatting/lint and package consistency checks.
- Secret scanning reviewed 15 findings: explicit local-only database credentials, mock provider values and the scanner package version string. Exact hashes are baselined; new findings fail CI. Local environment files, database data and generated artifacts are excluded from Git. Frontend production dependency audit and the locked Python dependency audit found no known vulnerabilities. Test providers never use real credentials.

Screenshots: ignored `output/playwright/devhub-desktop.png` and `devhub-mobile.png`.

## Explicit limits and launch gates

- Real OIDC, GitHub and OpenAI account smoke tests require operator secrets and have not run. No generated AI result is fabricated when the provider is unconfigured.
- Docker is unavailable on this workstation. Compose/workflow YAML was parsed, but image builds, container smoke tests and hosted GitHub Actions must pass in the operator environment.
- Invitations add existing users by email; email-delivered invitation acceptance, notifications, full-text search, file attachments, billing and organization deletion/export are deferred.
- GitHub integrates repository metadata only; self-service installation callbacks, issue/PR mirroring and code ingestion are deferred. API installation/link verification is synchronous with bounded timeouts; load-test lock contention before large-scale adoption.
- Lists use bounded offset pagination. Project archive/privacy are API features; the first UI emphasizes creation, access and collaboration.
- AI outputs are persisted in the tenant database. Set and implement an approved output retention/deletion policy before processing sensitive production content. Provider-side exactly-once execution cannot be guaranteed across a worker/process crash; reserved failed/in-progress requests still consume quota.
- Managed TLS ingress, PostgreSQL TLS/backups/PITR, secret rotation, dependency monitoring, telemetry export/alerts, accessibility audit, load/soak tests, multi-zone deployment, MFA policy and measured recovery drills remain operator release gates.
- The parent repository still contains its original customer-churn files/history. DevHub imports none of them and this work does not edit them. CI workflows are the only new files outside `devhub/`.
