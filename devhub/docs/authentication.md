# Authentication setup and verification

DevHub supports GitHub OAuth, Google OAuth, and verified email/password accounts. They share the existing `users`, `identities`, and opaque server-side `sessions` tables. This change does not implement invitations. The GitHub repository-integration App remains separate from login.

## Configuration

Configure these backend environment variables in Render. Never prefix secrets with `VITE_`, enter them in source, or paste them in chat. Nothing here requires `OIDC_ISSUER`, `OIDC_CLIENT_ID`, or `OIDC_CLIENT_SECRET`.

| Variable | Purpose | Secret |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID` | Google OAuth Web application client ID | No |
| `GOOGLE_CLIENT_SECRET` | Matching Google client secret | Yes |
| `GITHUB_CLIENT_ID` | Existing GitHub OAuth App client ID | No |
| `GITHUB_CLIENT_SECRET` | Existing GitHub OAuth App client secret | Yes |
| `EMAIL_AUTH_ENABLED` | Set to `true` to enable email/password routes | No |
| `RESEND_API_KEY` | Resend sending API key, restricted to the sender domain where available | Yes |
| `EMAIL_FROM` | Verified sender address belonging to a domain you control | No |
| `APP_ORIGIN` | Exact public HTTPS origin, without a path | No |
| `ENVIRONMENT` | Keep `production` on Render | No |
| `DEV_AUTH_ENABLED` | Keep `false` on Render | No |

Existing `DATABASE_URL` and optional `WORKER_DATABASE_URL` remain unchanged. No runtime password is created or altered by this migration. Missing OAuth credentials disable only that provider. Email login requires the email feature flag; signup, recovery and verification resend also require email delivery configuration. Configured buttons do not prove the remote credentials are valid.

`DEV_AUTH_ENABLED` is a local-only, passwordless test identity mechanism. It requires a development/test environment and loopback origin; production rejects it. To test real auth locally, disable this flag.

## Google Developer Console

1. Use an existing Google Cloud project, or create a project without activating paid services or billing. Open Google Auth Platform (OAuth consent screen / APIs & Services credentials in older console layouts).
2. Complete Branding, support email and developer contact information. Configure the audience appropriate to your users; for an External app in Testing, add the Google accounts used for testing.
3. Request only `openid`, `email`, and `profile`. This app does not request Google APIs, Drive data, offline access, or refresh tokens.
4. Create an OAuth client of type **Web application**. Register this exact production Authorized redirect URI:

   `https://devhub-ai-z6gw.onrender.com/auth/google/callback`

5. For local testing with `APP_ORIGIN=http://localhost:5174`, register `http://localhost:5174/auth/google/callback`. Use a separate development client where practical. There is no browser Google SDK, so JavaScript origins are not used by this server-side flow.
6. Enter the client ID and secret privately in Render. Before opening sign-in to everyone, review Google's audience/publishing requirements and move out of Testing when appropriate.

Google uses authorization code + PKCE with random state, a nonce, browser binding and a single-use database flow. The backend verifies RS256 signature, issuer, audience, expiration, nonce and verified email using Google's fixed token/JWKS endpoints. Google ID tokens and access tokens are not stored or returned to the browser. GitHub continues using its access-token flow, **not** OIDC or ID-token validation.

Official instructions: [Google Web Server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [Google OpenID Connect verification](https://developers.google.com/identity/openid-connect/openid-connect).

## GitHub configuration

Keep the existing GitHub OAuth App and callback `https://devhub-ai-z6gw.onrender.com/auth/callback`. Local callback: `http://localhost:5174/auth/callback`. The existing `/auth/login` and `/auth/callback` routes remain unchanged. Login needs a primary verified GitHub email. Repository integration still uses its existing App ID, private key, webhook secret and installation bindings.

## Email delivery

The email adapter uses Resend's HTTPS API; it does not require SMTP or a background worker service.

1. Use a free Resend account without activating paid billing. Leave **Transactional Overages / pay-as-you-go disabled** and review the [current free-tier quotas](https://resend.com/pricing). Verify an **existing domain you control** using the provider's DNS records and choose an approved sender for `EMAIL_FROM`.
2. Create a sending API key and set `RESEND_API_KEY` privately in Render.
3. Set `EMAIL_AUTH_ENABLED=true` after sender setup. Do not use invented addresses or keys.
4. Verify delivery to a real inbox and check spam. Provider test senders may restrict recipients and are not a substitute for a verified production sender. If you do not have a suitable domain, email delivery remains blocked on sender setup; no domain purchase or paid plan is authorized by this implementation.

Delivery runs after the generic HTTP response, with a timeout and safe failure logging, to avoid revealing account existence through provider errors. Tokens are committed before delivery. Sending is best-effort in this single-process deployment: a restart or provider failure can lose an in-flight message. Users can request another link; old links of the same purpose are invalidated. Monitor the generic `Authentication email delivery failed` log and provider delivery dashboard. Do not log provider bodies, recipients, or token-containing URLs. Review free-tier quotas before public use; account/global limits are safeguards, not a provider spending guarantee.

Official API: [Resend send email](https://resend.com/docs/api-reference/emails/send-email).

## Migration and Render rollout

1. Confirm the deployed branch contains the new auth files and migration `0003_auth`, alongside the existing host-header fix. Do not deploy the old generic OIDC implementation on `main` by accident.
2. In a trusted operator session with the **existing schema-owner database credential injected privately**, set `PROCESS_ROLE=migration` and run, from `devhub/`:

   ```sh
   python -m alembic -c backend/alembic.ini upgrade head
   ```

   Never substitute the owner credential into the web service environment. This migration adds `password_credentials`, `email_tokens`, `auth_throttles`, and nullable `oidc_flows.link_session_hash`. It grants access to the existing `devhub_app` role when present. Worker access is not granted. Existing users, identities, sessions, memberships and passwords are not rewritten. New databases should continue to run the existing restricted-role provisioning process separately.
3. In the existing Render service, add the variables above and keep `APP_ORIGIN=https://devhub-ai-z6gw.onrender.com`, `ENVIRONMENT=production`, `DEV_AUTH_ENABLED=false`. Leave database credentials and working host/deployment settings unchanged. Keep OpenAI credentials unset.
4. Build/deploy the updated application and frontend together. `/health/ready` now expects `0003_auth`; the previous release expects `0002_ai`, so schedule the migration/deployment together and expect a brief readiness transition.
5. Verify `/health/ready` returns 200 and `/auth/session` reports the enabled providers and email flags without secret values. Then perform the production checks below. No production migration, real OAuth authorization, or actual email delivery is performed by automated local tests.

## Flows and security decisions

- Signup validates email and a 15–128 character password; common/repetitive passwords are rejected. Passwords use salted scrypt (`N=32768`, `r=8`, `p=3`) with bounded hashing concurrency. No plaintext passwords are stored. Verification is required before email login.
- Duplicate signup returns the same generic 202 response as a new request, with no additional account. The email owner chooses their final password on the verification page, so a malicious preregistration cannot preserve a known password. Resend verification is available.
- Forgot password returns the same generic 202 response for unknown, OAuth-only, disabled and eligible password accounts. It never creates a password on an OAuth-only account.
- Reset/verification links use random 256-bit tokens, stored as SHA-256 hashes with 30-minute expiry. The token is in a URL fragment; the frontend removes it from the address bar and submits it in a POST body. Single-use consumption is serialized on the credential row. Reset revokes **all** user sessions and requires a fresh login.
- Password endpoints enforce exact Origin checks and database-backed limits: per action 30 requests/minute globally and 5 attempts/15 minutes per account or token. These persist across process restarts; they intentionally trade some demo availability for abuse resistance. HTTP 429 includes Retry-After. Existing session CSRF checks and secure cookie flags are retained.
- Matching emails are not enough to link identities. A new provider matching an existing account is rejected with instructions to sign in using the existing method. After signing in, use **Connect Google/GitHub** in the sidebar; the CSRF-protected action requires a session created within five minutes and binds the provider callback to that same active session. The callback must complete within ten minutes. A provider already attached to another user cannot be taken over. No automatic account merging, unlinking, or historical duplicate-account migration is included.
- Browser OAuth cancellation/failure redirects to a safe login error state; no provider error text, codes or tokens are reflected into the page.

## Local checks

From `devhub/`, configure the ignored local environment using `.env.example` (never commit it). Use the existing local PostgreSQL setup and isolated test database. Run:

```sh
.venv/bin/python scripts/manage.py migrate
.venv/bin/python scripts/manage.py test -q
.venv/bin/ruff check backend scripts
.venv/bin/ruff format --check backend scripts
.venv/bin/python -m compileall backend
npm test --prefix frontend
npm run build --prefix frontend
git diff --check
```

For interactive testing, run the existing backend/frontend development commands with `DEV_AUTH_ENABLED=false`, local `APP_ORIGIN`, and privately configured test provider credentials. OAuth tests use mock transports with genuinely signed test Google JWTs; email tests capture messages in memory and never make provider calls. No fake provider mode is deployed.

## Local and production manual acceptance checklist

1. **Google:** sign in with a new verified Google identity; verify a workspace account/session is created. Log out and sign in again; confirm the same user and workspaces. Cancel consent, retry with expired state, and confirm a helpful retry screen. Existing email collisions must request explicit linking.
2. **GitHub:** repeat new/existing user and cancellation tests. Confirm callback remains `/auth/callback` and repository integration is unaffected.
3. **Signup:** fill name/email/password/confirmation. Try malformed email, short/common password and mismatched confirmation. Submit a valid account; it must not sign in before verification. Open the received verification link, choose/confirm your password, then log in. Duplicate signup must not create another account.
4. **Forgot/reset:** submit known and unknown emails; compare the same generic confirmation. Open the actual email link, choose a new password, and confirm all existing sessions are signed out. Old password must fail; new password must work. Reuse the link, request a replacement link, and test a link after 30 minutes; invalid links must fail without changing the password. Do not paste emailed links into logs or chat.
5. **Linking:** sign in again, choose Connect Google/GitHub in the sidebar, and complete provider consent. Logout and sign in using the newly connected provider; the user ID, organizations and workspaces must remain unchanged. Attempt to connect an identity already owned by a different account; it must fail.
6. **Session/security:** logout then request a protected API route; expect 401. Test a mutation without CSRF or with an unrelated Origin; expect 403. Confirm production cookies are Secure/HttpOnly/SameSite=Lax, development login is unavailable, and rate limits return 429 after repeated attempts.
7. **UI:** check login, signup, recovery, verification and account connections on desktop and mobile. Check console/network failures without exporting request bodies or OAuth URLs containing sensitive data.

## Implementation file manifest

Paths relative to `devhub/`:

- Backend: `backend/devhub/auth.py`, `auth_models.py`, `config.py`, `main.py`, `http_limits.py`; new `auth_mail.py`, `email_auth.py`, `google_auth.py`, `passwords.py` in that same directory.
- Database: new `backend/migrations/versions/0003_auth.py`.
- Backend tests: `backend/tests/test_auth.py`, `test_deployment.py`; new `test_email_google_auth.py` in that directory.
- Frontend: `frontend/src/App.tsx`, `api.ts`, `styles.css`, `types.ts`; new `AuthScreen.tsx` in that directory.
- Frontend tests: `frontend/src/test/workspace.test.tsx`; new `frontend/src/test/auth.test.tsx`.
- Configuration and documentation: `.env.example`, `.secrets.baseline` (existing fixture line metadata only), `compose.yaml`, `scripts/serve_free.py` (remove new auth secrets from worker environment), `README.md`, `docs/security.md`, and this guide.

Local verification: 103 backend tests, 11 frontend tests, production frontend build, migrated-schema comparison, Ruff lint/format, Python compilation, secret scan including new files, and frontend production dependency audit passed. Existing desktop/mobile workspace browser journeys passed. Separate real local browser journeys covered signup, verification, login, logout, forgot/reset and replacement-password login on desktop/mobile with private synthetic email capture. Google token verification was tested with signed mock JWTs, not a real Google account. Live OAuth credentials, actual email delivery, and production migration/deployment remain operator rollout steps.

## Email/password completion update

Signup now collects First Name and Last Name, storing their combined value in the
existing users.display_name column. Existing display_name clients remain compatible.
The UI requires password confirmation; the API rejects supplied mismatches.
Verification still asks the email owner to choose the final password, preserving
protection against malicious preregistration. No phone or SMS fields were added.

The sidebar offers Change password for email-enabled deployments.
POST /auth/change-password requires the existing session, CSRF token, exact Origin,
current password, and a strong new password plus matching confirmation. Verified
password accounts only are eligible. It locks the credential, hashes the replacement,
revokes every user session and deletes outstanding email tokens. The UI returns to
login. OAuth-only accounts continue using their provider; both OAuth implementations
and safe linking rules are unchanged.

Resend emails now contain professional HTML plus plain text. Both link formats use
APP_ORIGIN and token fragments. Sending remains best-effort with safe generic failure
logs; users can request a replacement. No welcome email or paid service was added.

### Deployment steps for this update

1. Review, commit and push the approved diff to the branch used by the existing
   Render service. This update has not been committed or pushed.
2. Production is reported to already be at 0003_auth. No new migration, table,
   ownership grant or privilege change is needed. Startup should perform a no-op
   upgrade and verify the schema. Do not stamp revisions.
3. Keep DATABASE_URL and any WORKER_DATABASE_URL unchanged. Configure the existing
   backend environment variables: EMAIL_AUTH_ENABLED=true, RESEND_API_KEY,
   EMAIL_FROM, APP_ORIGIN=https://devhub-ai-z6gw.onrender.com,
   ENVIRONMENT=production, DEV_AUTH_ENABLED=false. Preserve GOOGLE_CLIENT_ID,
   GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET. Keys and secrets
   belong only in Render. No new variable names are needed in .env.example.
4. Verify the existing sender/domain in Resend and ensure it can send to real
   recipients. Do not enable paid overages. Google and GitHub callback paths remain
   /auth/google/callback and /auth/callback under the production origin.
5. Rebuild/deploy the existing Docker service. Inspect migration startup logs,
   require HTTP 200 from /health/ready, and check /auth/session for email_enabled,
   email_delivery and provider availability. Flags alone do not prove delivery.
6. Sign up with a real inbox. Test verification email delivery, production link,
   login before/after verification, duplicate signup, resend, expired/reused tokens,
   forgot/reset, and logout. Old passwords and sessions must fail after reset.
7. Log in and test Change password: incorrect current password, mismatched
   confirmation, then success. Check another device is signed out. Test both OAuth
   providers again, including cancellation and same-email linking behavior.

Local tests use actual isolated PostgreSQL and captured email transport. Adapter
tests validate production-origin HTML/plain-text Resend payloads with mock HTTP.
No actual emails or provider OAuth requests are sent by tests. Production environment
values, delivery, OAuth and health still need live verification. Same-origin frontend
requests preserve the existing Origin/CSRF policy; no CORS relaxation was added.

Files changed for this update: backend/devhub/email_auth.py,
backend/devhub/auth_mail.py, backend/tests/test_email_google_auth.py,
frontend/src/AuthScreen.tsx, frontend/src/App.tsx, frontend/src/test/auth.test.tsx,
and this document. Earlier uncommitted startup migration changes are preserved.
