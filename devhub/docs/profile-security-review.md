# Authentication and profile security review

Scope: the profile/settings and password-policy diff, including unchanged auth
boundaries it calls. No production data or external provider settings were inspected.

No unresolved critical/high issue was identified in this change. This is a focused
code and regression-test review, not a production penetration-test certification.

| Concern | Evidence / result |
| --- | --- |
| Authentication bypass / authorization | Every profile/avatar route uses auth.require_user. There is no caller-controlled user ID. Unauthenticated and cross-user avatar tests pass. |
| CSRF / Origin | Profile mutations use the same require_user dependency as existing protected writes. Raw image uploads send the session CSRF header; incorrect headers are rejected. No CORS, TrustedHost, cookie or origin policy is relaxed. |
| Account takeover / OAuth | OAuth callbacks and verified-email linking logic are unchanged. Profile PATCH forbids email, credential and identity edits. Existing provider regressions run against the new schema. |
| Passwords / session invalidation | One backend complexity validator serves signup, verification, reset and change. Existing scrypt parameters remain unchanged; old hashes remain accepted for login. Recovery/change revoke all sessions. Weak reset input does not consume a token. |
| Token leakage / enumeration | Existing token hashes, expiry, single-use locking, generic reset replies and email throttling remain. Reset tokens use fragments removed from the address bar and POST bodies, not logs/query URLs. No secret values are introduced. |
| Insecure uploads / traversal | profile.sanitize_image limits bytes, pixels, frames and concurrency; verifies actual format against MIME; decodes and re-encodes pixels with Pillow. No supplied filename/path/URL is stored or fetched. Raw input, EXIF and appended content are discarded. Tests cover spoofing, corruption, animation and oversized inputs. |
| XSS / user data | React renders names as text. Uploaded SVG/HTML are rejected. Avatars are freshly encoded JPEG with nosniff and no-store, available only to authenticated owners. Browser previews are data URLs from MIME-allowlisted local files; no raw HTML sinks are introduced. |
| Persistent storage | Bounded avatar bytes live in PostgreSQL, never Render's ephemeral disk. ORM binary data is deferred. Migration adds two nullable columns without grants, ownership or credential changes. |

Operational limits: images count against PostgreSQL's free storage quota; monitor it.
Resend remains the existing best-effort delivery adapter; a live inbox check is still
required. Production schema migration must use the authorized migration role rather
than elevating the web role. OAuth-only historical records have no stored verified
email claim; settings explicitly avoid inventing that verification state.

Image-processing design follows [Pillow image decoding and size-limit guidance](https://pillow.readthedocs.io/en/stable/reference/Image.html)
and [orientation handling](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose).
The database tradeoff, deployment and rollback implications are in
[profile-settings.md](profile-settings.md).
