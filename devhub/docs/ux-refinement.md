# DevHub experience refinement

## Audit and priorities

Source review covered every frontend component, API client/resource hook, existing tests, the authentication/profile handlers and models, permissions, environment contract, and combined Render Docker deployment.

Verified issues before implementation:
- Mobile sidebar used only a visual scrim: no focus containment, Escape close, or inactive-background handling.
- Password inputs had no reveal control. Profile/task/discussion drafts could be discarded without warning.
- Small text and faint hardcoded colors reduced readability; only light content surfaces existed.
- Dashboard illustration occupied substantial space without providing work context.
- Several failed resource loads offered no retry. Account/profile saving lacked distinct draft feedback.
- Members table relied on horizontal scrolling at narrow widths.

Implementation order: shared controls/tokens; shell/mobile navigation; profile and password experience; project/task/discussion refinements; responsive and browser regression verification.

## Decisions and scope

Keep React, Vite, Lucide, CSS and existing native dialog elements. Add semantic light/dark tokens and a system/light/dark selector; only the non-sensitive appearance preference is stored locally. Retain hash-based settings navigation and existing component-state workspace navigation. No fabricated activity or metrics. Replace the ornamental dashboard hero with a concise next action and actual project/member/role data.

Shared additions: PasswordField, Skeleton, ThemeControl, and a navigation/beforeunload draft guard. Existing Avatar, Alert, Modal, Empty, buttons and form styles remain reusable. Native confirmation is deliberately used for discarding drafts, avoiding a second modal/focus implementation. Profile drafts persist between settings sections; workspace navigation asks before discarding them. Task and discussion close/cancel protect drafts. Browser reload uses the browser's standard warning (subject to browser support/user interaction).

Regression risks: focus restoration, mobile background interactivity, password input semantics, settings draft state after save, theme contrast, and responsive table layout. Cover with component tests and real Chromium workflows at the supported widths. Real OAuth provider redirects and delivered email remain credential-dependent; mocked provider tests are not production certification.

## Backend, storage and deployment

No new backend contracts, database migration, dependencies, paid assets, hosting, or environment variables. Existing authenticated PostgreSQL avatar_data/avatar_version persistence remains unchanged: JPEG/PNG/WebP input, 1 MiB/8 MP limits, sanitized JPEG output <=100,000 bytes. Render's ephemeral filesystem is not used. Authentication, hashing, OAuth, sessions, reset tokens and server-side permissions are preserved. AI remains unavailable without its existing configuration; no paid requests are made.

Changes are local for review. No deployment or push is part of this task.

## Validation record

- `npm test --prefix frontend`: 30 component/unit tests passed, including password visibility, draft cancellation, blocked preference storage, existing authentication, profile and workspace tests.
- `npm run build --prefix frontend`: TypeScript and Vite production build passed. No added dependencies; JS output is approximately 235 kB (69 kB gzip).
- `.venv/bin/python -m pytest -q`: 159 tests passed on isolated local PostgreSQL `devhub_test`, never production. Existing Starlette/Alembic deprecation warnings remain.
- `.venv/bin/python -m ruff format --check backend scripts`, `.venv/bin/python -m ruff check backend scripts`, `git diff --check`: passed.
- Tracked and untracked project source secret scan using the existing detect-secrets baseline: passed.
- Playwright: real local backend/database journeys for organization/project/task/discussion creation, avatar upload/removal and reload persistence, profile edits, logout and disabled AI state. Auth-screen provider/session and email responses are explicitly mocked in `auth-experience.spec.ts`; these are UI checks, not live provider verification.
- Browser screenshots and layout assertions: 320, 375, 390, 768, 1024 and 1440 px, light/dark. System appearance uses matchMedia with a persisted optional override. Inspected overview, profile, login, task dialog/board and member layouts; corrected dark empty-state surfaces, muted-action contrast and mobile table styling. Navigation checks cover Escape, focus containment/restoration, inert content, draft cancellation and browser Back. Screenshots are ignored artifacts under `output/playwright/`.

## Remaining limits

No live Google/GitHub OAuth, GitHub App installation, email-delivery or paid AI requests were made. Their production credentials and configuration are unchanged. Physical iOS/Android, Safari, assistive-technology and a complete WCAG conformance audit remain manual acceptance checks; Chromium emulation does not certify them. Native beforeunload prompts depend on browser policy. No new infrastructure setup is required. A later approved deployment needs the existing frontend build; no new migration is introduced here.

Final browser result: 7 passed, 1 intentionally skipped duplicate (the viewport-matrix test runs once and explicitly covers all six widths). After the final member-text contrast adjustment, the targeted six-width/two-theme test passed again. No horizontal page overflow was detected in those checks. The source diff remains uncommitted and unpushed.
