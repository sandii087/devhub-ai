# DevHub

A developer collaboration workspace built independently in `devhub/`. It imports no customer-churn code or data. React/TypeScript supplies the responsive frontend; FastAPI, SQLAlchemy, Alembic and PostgreSQL provide the API and persistence.

Implemented: organizations and roles, private projects and grants, versioned tasks, discussions/replies, OIDC sessions, signed GitHub webhooks and metadata synchronization, and opt-in AI drafting. See [verified milestones and remaining launch gates](docs/progress.md).

## Run locally

Requires Python 3.12+, Node 24+ and PostgreSQL. Run commands from this directory. Preserve an existing `.env`; use `.env.example` as a reference.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
npm ci --prefix frontend
```

Configure `DATABASE_URL`, a separate disposable `TEST_DATABASE_URL`, `APP_ORIGIN=http://localhost:5174`, `ENVIRONMENT=development` and `DEV_AUTH_ENABLED=true` in `.env`. The explicit development login accepts a local email/name without sending email. Never enable it on a public deployment.

On this macOS workstation, an optional local PostgreSQL helper avoids requiring Docker. It preserves existing data, creates development/test databases if missing and writes ignored connection configuration to `.local/database.env`:

```sh
.venv/bin/python -m pip install '.[local-postgres]'
.venv/bin/python scripts/local_database.py
.venv/bin/python scripts/manage.py migrate
.venv/bin/python scripts/manage.py serve
```

In separate terminals:

```sh
npm run dev --prefix frontend -- --strictPort
.venv/bin/python scripts/manage.py worker
```

Open **http://localhost:5174**. The API listens on `127.0.0.1:8001`; Vite proxies same-origin requests. `/health/live` and `/health/ready` are probes. Development API documentation: http://localhost:8001/docs. The helper uses an owner account for local convenience; production API startup rejects owner/superuser/BYPASSRLS accounts.

Alternatively, with Docker installed, `docker compose up --build` starts PostgreSQL, migrations, distinct runtime database roles, API, worker and frontend at **http://localhost:8080**. Compose credentials are explicitly local-only. This container route is configured but has not been executed on the current host, which has no Docker runtime.

## Verify

```sh
.venv/bin/python scripts/manage.py test -q
.venv/bin/python scripts/manage.py check-schema
.venv/bin/ruff check backend scripts
.venv/bin/ruff format --check backend scripts
npm test --prefix frontend
npm run build --prefix frontend
```

With both local servers running, from `frontend/` run `npx playwright install chromium` then `npx playwright test`. Browser tests create uniquely named local test workspaces; screenshots are ignored under `output/playwright/`. Backend tests require an isolated PostgreSQL database and use a restricted runtime role to exercise row-level security.

## Provider configuration

- **OIDC:** configure issuer, client ID and client secret; register `APP_ORIGIN/auth/callback`. The implementation requires verified email and discovery endpoints on the issuer's HTTPS origin. Confirm compatibility with the chosen provider. Sessions are opaque, revocable, browser cookies with CSRF/origin checks; tokens never enter browser storage.
- **GitHub:** configure a read-only GitHub App, PEM private key, webhook secret and operator-verified `GITHUB_INSTALLATION_BINDINGS` (`installation_id:organization_uuid`, comma separated). Use `APP_ORIGIN/api/v1/webhooks/github` as webhook endpoint. Administrators register installations and link repositories; run the worker to synchronize metadata. Repository code is not imported or executed.
- **AI:** supply `OPENAI_API_KEY` and an explicit `OPENAI_MODEL`. An administrator enables each project. Contributors choose whether to include the project description and recent task titles/descriptions. Requests use the Responses API with `store=false`, no tools, bounded output and database quotas. Outputs are drafts and never automatically change tasks or repositories. Provider retention terms still apply; `store=false` does not guarantee zero retention.

## Architecture and deployment

- [Architecture and decisions](docs/architecture.md)
- [Requirements and plan](docs/plan.md)
- [Database and API boundaries](docs/contracts.md)
- [Security model](docs/security.md)
- [Testing and operations](docs/operations.md)
- [Implementation evidence and limitations](docs/progress.md)

Root `.github/workflows/devhub-ci.yml` contains CI; `devhub-release.yml` is manually triggered and gates immutable GHCR images and optional SSH deployment behind protected environments. It does not automatically deploy on push. Configure GitHub environment approvals, credentials and an operator-provisioned host before use. `deploy/compose.production.yaml` is a single-host starting point, not the multi-zone reference architecture. See operations for configuration and recovery gates.
