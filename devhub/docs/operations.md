# Testing, deployment, and operations

## Verification strategy

Unit tests cover role decisions, state transitions and input limits. API integration tests use isolated data and exercise authentication, CSRF, organizations, private projects, task conflicts, discussions and webhook signatures. PostgreSQL-specific tests run against actual PostgreSQL with a non-owner runtime role: policies, composite foreign keys, locks, migrations and rollback must not be certified by SQLite tests. Frontend component tests cover loading/errors/forms; browser tests cover complete collaboration journeys and keyboard navigation. Provider tests use deterministic HTTP fakes; a real OIDC/GitHub installation smoke test is a separate launch gate.

CI installs locked dependencies, checks formatting/types, runs backend tests, migrates a disposable PostgreSQL database, builds the frontend, executes browser tests, scans dependencies/secrets, and builds containers. Treat contract changes and migration safety as reviewable gates. Do not regenerate the old churn pipeline to test DevHub.

## Production reference topology

CDN serves private object-storage static assets and forwards `/api/v1` and `/auth` without caching to an HTTPS load balancer. Two or more API replicas run across two zones; background workers run separately. PostgreSQL uses managed multi-zone storage, encrypted backups and point-in-time recovery. Secrets use a managed secret store/KMS. This maps to AWS CloudFront/S3, ALB/ECS Fargate, RDS PostgreSQL, Secrets Manager and CloudWatch/OpenTelemetry, but no cloud is provisioned by the repository.

Only ingress is publicly reachable. API/worker/database live in private subnets; database security groups allow application identities only. Restrict load-balancer access to the CDN and validate its origin header. Outbound access is limited to required provider services. Use TLS to database and external services. A pool budget must include every process and worker: total configured connections plus migrations/operations headroom must remain below the DB limit. Scale workers by queue age and bounded concurrency rather than unbounded spawning.

Fixed cost drivers are database redundancy, API replicas, NAT/ingress and telemetry; variable costs include traffic, logs, storage/backups and provider calls. Measure and budget these before selecting instance sizes. No unverified price estimates are part of this design.

## Release and recovery

Build one immutable versioned image per revision; promote that artifact between environments. Run migrations once as a restricted release job, never concurrently in every API startup. Expand/backfill/contract schema changes; old and new application versions must coexist during rollout. Gate traffic on readiness. Roll back the application only while schema-compatible; destructive down migrations are not an automatic rollback strategy.

Liveness checks process health; readiness verifies database reachability and migration compatibility. Emit structured request IDs, latency/error metrics, denied authorization events, database pool utilization, worker queue age/retries and provider status. Never log cookies, auth codes, tokens or full content. Alert on sustained error-budget burn, elevated auth failures, database exhaustion and stale integration jobs. Establish an on-call owner and runbooks before launch.

At least quarterly, restore into an isolated environment, verify integrity, reapply deletion tombstones, test authorization, measure RPO/RTO and only then switch traffic. Exercise database failover, worker termination after external effects, duplicate/reordered webhooks, expired secrets and unavailable OIDC. The targets in architecture.md remain unverified until those drills run.

Managed backups and load-balancer routing are provider capabilities; they still require explicit provisioning and restore validation. [RDS backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html), [ECS load balancing](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/alb.html).

## Supplied release template

The included production Compose template uses a single host with external managed PostgreSQL and HTTPS ingress. It does not provision the multi-zone reference design. Install `deploy/release.sh` and `deploy/compose.production.yaml` in `/opt/devhub` on a controlled host, with protected `api.env`, `worker.env`, and `migrations.env` files (mode 0600). Never commit these files.

API configuration requires `ENVIRONMENT=production`, `PROCESS_ROLE=api`, `DEV_AUTH_ENABLED=false`, HTTPS `APP_ORIGIN`, OIDC settings and a restricted `devhub_app` database URL. Worker configuration uses `PROCESS_ROLE=worker`, production/HTTPS settings, `devhub_worker` database URL and GitHub App credentials; it does not need OIDC or OpenAI secrets. Migration configuration uses `PROCESS_ROLE=migration`, a dedicated schema-owner URL and `DB_APP_PASSWORD`/`DB_WORKER_PASSWORD` to provision restricted roles. Use TLS database URLs (`sslmode=verify-full` with managed CA configuration).

Configure protected GitHub `release` and `production` environments. The manual release workflow builds immutable image digests after checks; optional deployment requires the SSH host/user/key and pinned known-hosts secrets named in the workflow. The deployment account must already be authenticated for GHCR and permitted to run Docker. Preserve previous successful image digests before each rollout. The release script never performs destructive database downgrades. For a failed rollout, investigate readiness, then restore compatible prior image digests; restore a database only through an approved recovery drill.

Local verification has not run container builds, hosted workflows, real provider smoke tests or recovery/load drills. Existing request logs and health probes are a foundation; external metrics, alerting and tracing require integration.
