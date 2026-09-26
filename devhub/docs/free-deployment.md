# Free-only deployment

Status: prepared locally; **no production URL is deployed or verified yet**. Cloud account access, external database provisioning and GitHub OAuth registration remain required. Never interpret this configuration as authorization to enable a paid plan or add a payment method.

## Architecture

`Dockerfile.free` builds the existing React frontend and serves it from FastAPI on one HTTPS origin. `scripts/serve_free.py` starts the API and, when `WORKER_DATABASE_URL` exists, a separate restricted worker process in the same web-service container. The worker polls once per minute while the service is awake; there is no paid background-worker service. Render may suspend the entire service while idle. Leases and persistent PostgreSQL jobs support recovery after a restart. No uptime pings or artificial traffic prevent sleeping.

The dedicated production Docker/Compose configuration remains available. The combined deployment adds coarse instance-wide limits (30 auth starts/callbacks and 120 mutations per minute). These are portfolio limits, shared among users, not a distributed production rate limiter.

## Verified service terms and prerequisites

- Render **Free web service**: $0 instance, shared 750 free instance hours/month, sleeps after 15 minutes without incoming traffic. Build/bandwidth quotas apply. A workspace with a payment method can incur overages: verify no payment method and stop if card verification or an upgrade is required. See https://render.com/docs/free and https://render.com/docs/faq.
- Neon **Free PostgreSQL** candidate: 0.5 GB storage, 100 CU-hours and 5 GB network transfer per project/month, scale-to-zero after five idle minutes. Quota exhaustion can suspend compute until the next period. The worker's polling can keep database compute awake while Render is running; monitor quota and allow normal sleep. No paid Neon plan is permitted. See https://github.com/neondatabase/website/blob/main/content/faqs/free-plan-limits-and-quotas.md.
- Authentication uses a GitHub OAuth App, separate from the repository integration GitHub App. Auth0 is no longer used by the application. No paid authentication service is required.
- OpenAI: **not configured**. No key, model or AI billing is provisioned. No real AI requests are part of deployment validation.
- Render Free PostgreSQL is deliberately excluded because its database expires after 30 days. No Render database, paid worker, disk, cron, domain or other paid resource appears in the Blueprint.

## Deploy in order

1. Sign in privately to Render, Neon and GitHub. Confirm all plans are Free and no payment method/usage billing is active. Do not share secrets in chat.
2. Create a dedicated non-expiring Neon Free database only after reviewing the above quotas. Use TLS. Run Alembic migrations with a schema-owner credential in a trusted operator session, then `scripts/provision_roles.py` with generated runtime passwords supplied privately through environment variables. Keep the owner credential out of the runtime service. Neon console-created roles can have elevated privileges: use the script-created `devhub_app` and `devhub_worker` roles. Never bypass the API startup check rejecting owner/BYPASSRLS roles.
3. Import the repository on Render, selecting Blueprint path `devhub/render.yaml`. The service is explicitly `plan: free`, root `devhub`, Dockerfile `Dockerfile.free`. Verify the final creation screen still says Free/$0. Do not create it if any payment step is shown.
4. Set `APP_ORIGIN` to the actual HTTPS `onrender.com` URL. Register exactly `APP_ORIGIN/auth/callback` in the GitHub OAuth App. Users need a verified primary GitHub email. GitHub is not an OIDC issuer; the backend never discovers endpoints or validates an ID token. Replace any previous Auth0/OIDC deployment variables with the GitHub OAuth credentials below.
5. Enter the variables below directly in Render's environment-variable system. Do not put them in the Blueprint, source, frontend build, logs or GitHub. Deploy only after migrations and GitHub OAuth are ready.
6. Validate `/health/ready`, homepage, real GitHub OAuth login/logout, organization/project/task/discussion permissions and responsive UI. Register a read-only GitHub App and its signed webhook if integration is required; validate installation ownership and add an operator binding. Verify an actual metadata sync after wake-up.
7. Check runtime logs without revealing secrets. Record the verified production URL in README only after successful browser verification. No live deployment has been verified yet.

## Runtime environment

| Variable | Value/purpose |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DEV_AUTH_ENABLED` | `false`; never enable on a public URL |
| `APP_ORIGIN` | Exact HTTPS service origin, no trailing path |
| `DATABASE_URL` | TLS PostgreSQL SQLAlchemy URL using restricted `devhub_app` |
| `WORKER_DATABASE_URL` | TLS URL using restricted `devhub_worker`; required for queued GitHub synchronization |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | GitHub OAuth App login credentials; backend only |
| `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET` | Optional read-only GitHub App configuration |
| `GITHUB_INSTALLATION_BINDINGS` | Operator-verified installation-to-organization mapping |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | **Leave unset for this deployment** |

`PORT` is supplied by Render; `FRONTEND_DIST` is supplied by the image. Set worker configuration in Render after provisioning the restricted role. Without it, core collaboration works but queued synchronization does not run.

Render also supplies `RENDER_EXTERNAL_HOSTNAME`. The backend allows that exact service hostname alongside the `APP_ORIGIN` hostname and existing local health/test hosts; other `onrender.com` services remain rejected. Do not configure a wildcard. Keep `APP_ORIGIN` equal to the public HTTPS origin used for login: it still controls OAuth callback URLs and CSRF origin validation. After updating host-validation code, rebuild and redeploy the existing web service using `Dockerfile.free`; no database migration or database environment changes are needed.

## Future AI activation

The application boundary is `AIProvider.generate(kind, prompt, context)`. `OpenAIResponsesProvider` retains the real Responses API implementation. Missing key or model fails closed before opening an HTTP client; the UI reports the provider unavailable and disables generation. No fake output or alternate AI implementation exists. Core collaboration is independent of provider availability.

Only after explicit approval for API charges, set the key and a selected model privately in Render, restart the service, and opt in each project. Existing authorization, context consent, idempotency, quotas, timeout, bounded output and plain-text rendering remain in force. Activation requires real provider smoke tests at that time.
