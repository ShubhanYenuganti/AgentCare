## Why

The backend agent system is feature-complete but has no real UI and no automated test coverage. The dashboard is currently a placeholder, and the entire spec-defined caregiver workflow (Action Feed, Patient Roster, Caregiver Management, Org Dashboard) is unimplemented. Without this work, the system cannot be demonstrated or validated end-to-end.

## What Changes

- Build the full four-view dashboard (`AppShell`, `TopBar`, `NavTabs`) with all spec-defined components
- View 1 — Action Feed: `ActionFeed`, stateful `ActionCard` variants (health-modify, non-health Q&A, scheduling deep-link), `ActionChatPanel`, `DraftModal`, overdue/tier banners, modification-in-progress lock, draft version badge, update flash state
- View 2 — Patient Roster: split layout with sidebar + detail sections, add/update patient workflows with staged confirmation state machine + file upload, update-history rendering
- View 3 — Caregiver Management: scheduling strip, caregiver detail panel, 14-day schedule grid, assignment list, confirm/decline flows, deep-link preselect from Action Feed
- View 4 — Org Dashboard: org summary, protocol panels, caregiver roster, org metrics cards
- Add typed API client layer (`src/api/client.ts`, `src/types/index.ts`, polling hooks)
- Add integration tests for patient update submit/confirm/file flows + detection trigger side effects
- Add executor internal detect endpoint tests and fan-out behavior tests
- Add domain-specific deterministic detection tests (health + appointment + grocery + financial expected outputs)
- Add scheduling agent E2E selection tests (query → options → numeric select → status transition)
- Add dashboard E2E tests for all four views and critical UX state transitions
- Add overdue dedup notification tests for expiration loop
- Update README and add architecture + pipeline docs

## Capabilities

### New Capabilities

- `dashboard-action-feed`: Action Feed view with all card variants, chat panel, draft modal, lifecycle visuals
- `dashboard-patient-roster`: Patient Roster view with add/update workflows, staged confirmation, file upload, update history
- `dashboard-caregiver-management`: Caregiver view with scheduling strip, schedule grid, assignment flows, deep-link
- `dashboard-org-view`: Org Dashboard view with summary, protocol panels, metrics
- `dashboard-api-client`: Typed API client layer with polling hooks and shared types
- `backend-integration-tests`: Patient update pipeline, detection fan-out, and executor endpoint integration tests
- `domain-detection-tests`: Deterministic expected-output tests for all four domain workers
- `scheduling-e2e-tests`: Full scheduling selection lifecycle tests
- `dashboard-e2e-tests`: Four-view dashboard + UX state transition E2E tests
- `overdue-notification-tests`: Expiration loop dedup tests for dashboard and ASI:One channels

### Modified Capabilities

- `api-dashboard-live-data`: Dashboard polling hooks consume enriched patient/action API responses from the backend-domain-and-api-completion change

## Impact

- `dashboard/src/` — all new React components and views
- `dashboard/src/api/client.ts`, `dashboard/src/types/index.ts` — new typed client layer
- `tests/` — new integration, unit, and E2E test files
- `README.md` — updated documentation
- No `agents/` or `api/routers/` files touched (assumes backend-domain-and-api-completion landed)
