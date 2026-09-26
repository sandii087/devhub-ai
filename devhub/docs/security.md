# Authentication, authorization, and security

## Authentication

Use GitHub OAuth authorization code flow with PKCE S256 and `read:user user:email`. The backend stores hashed state, verifier, browser binding and expiry in the existing `oidc_flows` table. Its legacy nonce field contains a provider marker that rejects pre-switch OIDC attempts. Consume each flow before exchanging the code, even on failure. Use only fixed GitHub endpoints with TLS, bounded responses, no redirects and no environment proxies. Identify users by issuer `https://github.com` and numeric GitHub ID, requiring a primary verified email. Do not merge accounts by email. No discovery, ID-token validation or access-token persistence is used. Keep the existing secure cookies, session expiry/revocation and CSRF protections. [GitHub OAuth flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps).

Issue an opaque high-entropy session cookie; store only its hash, user and lifecycle data. Production cookies use Secure, HttpOnly, SameSite=Lax and host-only scope. Proposed expiry: 30 minutes idle, 12 hours absolute. Rotate on login and privileged elevation; revoke on logout or account disable. Sessions and authorization are checked on every request, so removed memberships lose access on subsequent requests. Use Origin validation plus a synchronizer CSRF token for mutations. Login callbacks use state/PKCE/browser binding instead of normal CSRF headers. No bearer tokens in localStorage.

Development login exists only for local evaluation with explicit configuration; production startup must fail if enabled. It is visibly labeled in the UI. It is not a substitute for provider verification.

## Authorization policy

| Action | Owner | Admin | Member | Viewer |
| --- | --- | --- | --- | --- |
| Read organization-visible projects | Yes | Yes | Yes | Yes |
| Read private projects | Yes | Yes | Explicit grant | Explicit grant |
| Contribute to visible project | Yes | Yes | Yes or grant | No |
| Maintain project/settings/grants | Yes | Yes | Maintainer grant | No |
| Invite/manage ordinary members | Yes | Yes | No | No |
| Grant/revoke admin or owner | Yes | No | No | No |
| Remove final owner | No | No | No | No |
| View/manage GitHub metadata | Yes | Yes | No | No |
| Delete organization | Yes, fresh authentication | No | No | No |

Project grants are maintainer/contributor/viewer. Organization viewer is an absolute write ceiling. Membership must be active; a historical project grant does not revive removed organization membership. Tasks can be assigned only to active members who can access the project. Resource checks apply to lists, counts, search, nested IDs, notifications and worker consumers as well as detail endpoints. UI hiding is not a control.

## Threats and controls

| Abuse path | Control | Verification |
| --- | --- | --- |
| Substitute another tenant/project ID | Composite FKs, scoped lookup, membership/project policy, tenant RLS | Two-tenant and private-project negative tests with real PostgreSQL |
| Promote self or remove every owner concurrently | Field allowlists, role ceiling, locked last-owner check | Viewer/admin escalation and concurrent owner tests |
| Steal/fix/replay session | Hashed cookies, rotation, expiry, revocation, no secret logging | Logout/expiry/reuse tests |
| Cross-site write or login substitution | Origin + CSRF; OAuth state/PKCE + browser binding | Missing/mismatched token and callback tests |
| Stored script in discussion | Render untrusted content as text; no raw HTML, safe links; restrictive CSP | Script/URL payload browser tests |
| Forge/replay webhook | Raw-byte HMAC, constant-time compare, durable delivery dedupe | Tampered payload and duplicate delivery tests |
| Link a victim's GitHub installation | Secure install association + provider ownership/installation verification | Foreign/unverified installation rejected |
| Exhaust resources | Request/body/string/pagination caps, ingress rate limits, timeouts, bounded worker retries | Oversize/slow-provider/load tests |
| Leak through telemetry/build | Redaction, least-privilege secrets, locked dependencies, secret scans | Log inspection and CI scans |

Use parameterized SQL, no shell execution or unsafe deserialization, explicit response schemas and generic operational errors. Trust forwarded headers only from the configured ingress; reject unexpected hosts. No wildcard credentialed CORS. The SPA and API share an origin. Secrets are injected at runtime and never compiled into frontend assets. Separate migration, API and worker database privileges; deny audit mutation to API roles. Audit role changes, membership changes, login outcomes, destructive actions and integration configuration without storing tokens or full content.

## Data lifecycle

Provisional policy: organization deletion disables access immediately and purges content after 30 days; encrypted backups expire within 35 days; minimal audit records retained 365 days. Raw webhook payloads expire after processing/debug retention and are bounded; sessions/attempts are swept after expiry. Legal retention, user export/erasure, and regional commitments need an owner-approved policy before production. Restores must reapply deletion tombstones before reopening traffic. These are target requirements; see progress for implemented/deferred controls.

## Implemented AI boundary

AI is disabled unless both operator provider configuration and administrator project consent exist. Callers choose context sharing; at most 30 recent tasks plus the project description are included. The server uses a fixed HTTPS Responses API endpoint, bounded input/output, no executable tools and `store=false`. Treat generated text as untrusted: the UI renders plain text and never executes it or writes it into a task automatically. Database quotas bound abuse; authorization is checked before the external call and again before saving/returning results. Audit events record consent changes. Output retention/purge and real-provider data-processing review are required before sensitive production use.
