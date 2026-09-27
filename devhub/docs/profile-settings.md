# Profile, settings and password policy

The existing session, OAuth, CSRF and recovery implementations are retained. Settings
use the application's lightweight navigation: `/#settings/profile`,
`/#settings/security`, and `/#settings/account`. Hash navigation supports refresh,
back/forward and direct links without introducing a second router or server catch-all.
Both the sidebar identity button and header avatar open settings. The separate sign-out
control remains available. Successful name/avatar changes update the shared session
state immediately. User-supplied names are rendered as text, never HTML.

## Passwords and recovery

One backend validator (`passwords.validate_password`) enforces 8–128 characters,
at least one ASCII uppercase letter, lowercase letter, digit, and non-whitespace
special character (including underscore). Signup, verification, reset and change
password all use it. The frontend mirrors these rules and shows requirements before
submission. Scrypt parameters and existing password hashes are unchanged. Existing
passwords remain usable; only newly selected passwords must meet the new policy.

Forgot-password responses remain generic. Reset links contain 256-bit random tokens
in URL fragments, are hashed in the database, expire after 30 minutes, and are
single-use. Failed password validation does not consume a valid token. Reset and
change-password revoke all existing sessions and outstanding email tokens. Normal
password changes require the current password and CSRF; OAuth-only users manage
passwords with their provider. Google/GitHub flows and verified local-email automatic
linking remain unchanged.

Email verification shown in settings is based on the local verified credential.
Historical OAuth identity rows do not store a verified-email value, so OAuth-only
accounts are labeled as provider-connected with local verification unrecorded rather
than falsely claiming an email verification status.

## API and storage

- GET/PATCH `/api/v1/me`: own profile only. PATCH accepts only display_name (1–100
  characters after trimming). Email and account identifiers cannot be edited.
- PUT `/api/v1/me/avatar`: raw JPEG/PNG/WebP bytes, with matching Content-Type and
  the existing session/Origin/CSRF protections. No multipart filenames or paths.
- GET `/api/v1/me/avatar`: authenticated user's own normalized JPEG, no-store.
- DELETE `/api/v1/me/avatar`: own avatar removal with Origin/CSRF protections.

Native file selection supports computer and mobile devices. Uploads are limited to
1 MiB, 8 megapixels and one frame. Pillow decodes and validates the image, applies
orientation, resizes to at most 256×256, and re-encodes fresh pixels to JPEG. Metadata,
GPS and trailing content are discarded. Output is capped at 100 KB. Processing has
bounded concurrency. SVG, animation, mismatched MIME and corrupt images are rejected.
No filenames are used, remote URLs fetched, or files written on Render.

Migration `0004_profile` adds nullable `users.avatar_data` (BYTEA) and
`users.avatar_version` (content digest). The existing persistent PostgreSQL database
is appropriate for bounded portfolio avatars and requires no new paid storage or
credentials. Data is deferred in ORM reads, so normal user queries do not load blobs.
Avatars count against database storage/backups: at 100 KB each, 1,000 avatars can
consume roughly 100 MB before database overhead. Monitor the free database quota.
A future object-store implementation can preserve these API boundaries.

## Review and deployment (not performed)

No production data, credentials, grants, ownership or hosting configuration is changed.
No environment variables are added. Retain APP_ORIGIN as the production HTTPS origin,
ENVIRONMENT=production, DEV_AUTH_ENABLED=false, and the existing OAuth/Resend variables.
Render's ephemeral filesystem is not used for avatar persistence.

After review, run `alembic -c backend/alembic.ini upgrade head` using the authorized
migration runner against production, then deploy the reviewed image. The production
runtime role should stay restricted. If startup migration credentials cannot ALTER
users, an authorized schema owner must apply 0004_profile separately; do not grant
ownership to the web role. Readiness now requires 0004_profile. Coordinate migration
and rollout; the old release expects 0003_auth. Downgrading 0004 drops avatar columns
and pictures, but no identity/password/session records. Take a backup before any
intentional downgrade. No migration downgrade is run by this work.

Verify production readiness, login, profile name save, avatar upload/reload/remove,
Google/GitHub sign-in, email recovery/reset, password changes and session revocation.
The native picker accepts JPEG/PNG/WebP; unsupported HEIC photos must be exported to
one of those formats. Local mocked email/OAuth tests do not establish live provider
availability or deliverability.
