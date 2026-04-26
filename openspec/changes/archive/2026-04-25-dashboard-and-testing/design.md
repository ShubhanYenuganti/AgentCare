## Context

The dashboard is currently a minimal React placeholder (`dashboard/src/`). The spec defines four fully interactive views backed by the FastAPI REST layer: Action Feed, Patient Roster, Caregiver Management, and Org Dashboard. The backend API is assumed complete (enriched patient/action endpoints, scheduling lifecycle, caregiver schedule) by the time this change lands.

Test coverage is essentially zero: no integration tests, no domain detection tests, no scheduling E2E tests, no dashboard E2E tests. This change delivers both the full UI and the test infrastructure in a single change because they share no files with the backend agent work and can land atomically.

## Goals / Non-Goals

**Goals:**
- Build all four spec-defined dashboard views with full component architecture
- Implement typed API client layer with polling hooks
- Add integration tests for patient update pipeline and detection trigger side effects
- Add deterministic domain detection unit tests for all four workers
- Add scheduling agent E2E selection tests
- Add dashboard E2E tests for all four views and critical UX state transitions
- Add overdue notification dedup tests for expiration loop
- Update README and add architecture/pipeline docs

**Non-Goals:**
- Backend agent logic, domain rules, or FastAPI routing (separate change)
- Mobile/native app (web dashboard only)
- Real-time WebSocket push (polling-based dashboard only)
- OAuth or multi-user auth flows

## Decisions

**D1: React + existing Vite + RTK Query for API client**
The dashboard already uses Vite. RTK Query (part of Redux Toolkit) provides the typed API client layer, polling hooks, and cache invalidation with minimal boilerplate. All API shapes are typed via `src/types/index.ts` generated from the FastAPI router contracts.
- Alternative: React Query (TanStack Query). Either works; RTK Query is preferred because it co-locates action mutations with the slice state for card lifecycle management.

**D2: Component architecture follows spec AppShell → view → card pattern**
`AppShell` owns `TopBar` + `NavTabs` + view outlet. Each view (`ActionFeed`, `PatientRoster`, `CaregiverManagement`, `OrgDashboard`) is a lazy-loaded route. `ActionCard` is a polymorphic component with three render variants (health-modify, Q&A, scheduling) selected by `domain + manual_action_type`.
- Alternative: One card component per variant. Rejected — too much duplication; polymorphic variant via props is cleaner.

**D3: Staged confirmation state machine in Patient Roster as local component state**
The add/update patient flow uses a local multi-step state machine (`idle → submitting → awaiting_confirmation → confirmed | cancelled`). No global Redux state — the flow is scoped to a single modal and doesn't need to persist across navigation.

**D4: Dashboard E2E tests via Playwright**
Playwright is the standard choice for Vite/React E2E — fast, supports component isolation, and has first-class TypeScript support. Tests run against the real FastAPI server started in a fixture.
- Alternative: Cypress. Rejected — Playwright has better async primitives and native ESM support with Vite.

**D5: Backend integration and domain unit tests via pytest with real SQLite**
Tests under `tests/integration/` spin up real SQLite in a temp dir, seed deterministic data, and assert detection outputs match expected `ActionDraft` shapes. No mocking of DB layer (consistent with existing test philosophy — see feedback memories).
- Alternative: Mock DB in unit tests. Rejected explicitly per project preference.

**D6: Overdue notification dedup tests assert on `notification_log` table entries**
The expiration loop writes to `notification_log` before dispatching. Tests verify that running the loop twice for the same overdue action produces exactly one log entry per channel (dashboard, asi_one).

## Risks / Trade-offs

- [API shape drift between backend change and dashboard] → `src/types/index.ts` is typed manually against the spec contracts. If backend-domain-and-api-completion adds fields, the dashboard types need a follow-up update. Risk is low since the proposal for that change is additive only.
- [Playwright flakiness on async polling UI] → Use `waitForSelector` with explicit timeout assertions rather than `waitForTimeout`. All async state changes are driven by API responses with deterministic seed data.
- [Domain detection tests are brittle if LLM prompt output varies] → Detection tests assert on rule-triggered drafts only (deterministic path), not LLM-added edge-case drafts. LLM drafts are excluded from expected-output assertions.
- [E2E test suite adds significant CI time] → Tests are tagged `@e2e` and can be excluded from fast CI runs with `pytest -m "not e2e"` / `npx playwright test --project=unit`.
