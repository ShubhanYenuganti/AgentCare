# TASKS — Remaining Features vs `MACOS_build_spec_v7_final.md`

Last audited: 2026-04-25
Audit basis: `MACOS_build_spec_v7_final.md` compared against current code.

Recent changes applied:
- `openspec/changes/backend-domain-and-api-completion` — 44/44 tasks done
- `openspec/changes/dashboard-and-testing` — 52/52 tasks done

## Snapshot

All major sprint goals are complete. Remaining items are refinement gaps.

## 1) Data Layer + Seed Gaps

- [x] Add missing life-graph tables to `data/schema.sql`
- [x] Expand `action_history` schema to include all spec fields
- [x] Align `expiration_notifications` columns
- [x] Update `agents/shared/db.py` serialization to full life graph from normalized tables
- [x] Add DB helper for scheduling chat-selection flow
- [x] Extend `data/seed.py` with normalized domain table data
- [x] Seed data supporting all domain detection checks
- [ ] Populate `asi_one_address` for at least one seed caregiver to enable ASI:One push testing

## 2) Executor + Internal Detection Pipeline Gaps

- [x] Implement executor internal endpoint `POST /internal/detect`
- [x] Implement `run_detection(patient_id, trigger, updated_domain)` flow
- [x] Inject domain-specific org context into each fan-out message
- [x] Implement expiration loop behavior (`@on_interval(900)`) with dedup
- [x] Add scheduling-task post-processing in supervisor-result handler
- [x] Implement action-chat processing via `POST /actions/{id}/chat`
- [x] Align intent handler surface: onboarding, scheduling query, action-bound modification/question, general fallback

## 3) Ingest + Patient Update Pipeline Gaps

- [x] Replace `/ingest/text` proxy with spec extraction flow
- [x] Add `POST /ingest/file` with PDF and image extraction
- [x] Implement `POST /patients/{id}/update` with LLM classifier
- [x] Persist proposed changes and return confirmation payload
- [x] Implement `POST /patients/{id}/update/{update_id}/confirm`
- [x] Implement `POST /patients/{id}/update/file`
- [x] Implement `GET /patients/{id}/update-history`
- [x] Ensure removal operations are soft-delete (`active=0`) across all normalized tables

## 4) Domain Supervisor/Worker Logic Gaps

### Health domain
- [x] Replace generic detection with explicit spec checks (refill due, missed dose, OpenFDA interaction, OpenFDA recall)
- [x] Implement OpenFDA live integration with timeout/retry/fallback
- [x] Add supervisor risk-scoring pass
- [x] Implement health modification pipeline (live-data aware, review pass, retry, changes summary)
- [x] Implement question pipeline live-API branching
- [ ] **Appointment worker — post-visit extraction** (Check 4 from spec §6.7): forward caregiver visit notes → LLM → structured life graph updates

### Appointment domain
- [x] Replace generic detection with explicit checks (overdue, transport, visit prep)
- [x] Add Google Maps integration (conditional on key)
- [x] Enforce scheduling-task output structure
- [ ] **Transport planning fallback**: produce transport draft even when `GOOGLE_MAPS_API_KEY` is absent (currently check is silently skipped)

### Grocery domain
- [x] Replace generic detection with explicit checks (staleness, dietary conflict, supply reorder)
- [x] Ensure mock API calls are in deterministic rule path
- [x] Normalize grocery actions to scheduling-task behavior

### Financial domain
- [x] Replace generic detection with explicit checks (bill due, missed autopay, anomaly)
- [x] Add anomaly pass using life-graph financial history

### Cross-domain supervisor behavior
- [x] Non-health modification guard (returns "not supported" for appointment/grocery/financial)
- [x] Q&A support across all four domains with optional live API worker path

## 5) Scheduling Agent + Scheduling API Gaps

- [x] Replace mock-only handler with `SchedulingQuery` flow
- [x] Implement scheduling options generation via `/mock/caregivers/available`
- [x] Add chat-selection handler (numeric choice / cancel)
- [x] Implement `POST /scheduling/{id}/assign`, `POST /scheduling/{id}/confirm`, `POST /scheduling/{id}/decline`
- [x] Add `POST /scheduling/{id}/cancel` (sets `scheduling_status="cancelled"`)
- [x] Decline flow frees slot, resets status, writes escalation notification

## 6) FastAPI Contract Gaps

- [x] CORS middleware (`DASHBOARD_ORIGIN` env var, default `http://localhost:5173`)
- [x] Enriched `GET /patients`: pending_action_count, overdue_action_count, highest_urgency_level
- [x] Enriched `GET /patients/{id}`: full life_graph, pending_actions, action_history
- [x] Enriched `GET /actions` with patient_name, is_overdue, scheduling_status fields
- [x] `POST /actions/{id}/dismiss`
- [x] `POST /actions/{id}/chat`
- [x] `GET /actions/{id}/chat-history`
- [x] `GET /caregivers/{id}/schedule` and `GET /caregivers/{id}/assignments`
- [x] `PUT /org` support
- [x] Approve path writes `completion_date` and `outcome`

## 7) Mock API Parity Gaps

- [x] Amazon reorder mock response fields aligned
- [x] Caregiver availability sort: assigned-first, 3 business days fallback
- [x] Coverage tests for all mock endpoints (`tests/test_mock_api_coverage.py`)

## 8) Dashboard Implementation Gaps

### View 1 — Action Feed
- [x] AppShell, TopBar, NavTabs (functional — not granular spec file structure)
- [x] ActionCard with health-modify, Q&A, and scheduling variants
- [x] Overdue and tier banners, modification-in-progress lock
- [x] ActionChatPanel (3s polling while open)
- [x] DraftModal with idempotency_key
- [x] Scheduling-card deep-link to caregiver view
- [ ] **Draft version badge** on ActionCard (reads `draft_version` from DB, not yet displayed)
- [ ] **Update flash state** on ActionCard (transient visual highlight when draft changes)
- [ ] **Notification bell** in TopBar (unread count badge from `GET /notifications`)

### View 2 — Patient Roster
- [x] Split layout with sidebar + detail panel
- [x] Urgency pills from enriched API response
- [x] Life graph sections (health, appointments, grocery, financial, emergency contacts)
- [x] Pending actions summary + action history accordion
- [x] Add Patient modal (text + file tabs)
- [x] Staged update confirmation state machine
- [x] Update History tab

### View 3 — Caregiver Management
- [x] Scheduling strip with pending/unconfirmed actions
- [x] Assignment dropdowns
- [x] Confirm and Decline buttons
- [x] 14-day schedule grid
- [x] Assignment list
- [x] Deep-link preselect from Action Feed

### View 4 — Org Dashboard
- [x] Org summary panel with counts
- [x] Protocol cards
- [x] Org metrics cards (pending, overdue, completion rate, avg urgency)
- [x] Caregiver roster table
- [x] Edit Org Profile form (`PUT /org`)

### API client layer
- [x] RTK Query API slice (`src/api/client.ts`) with all endpoints
- [x] TypeScript types (`src/types/index.ts`)
- [x] Polling: actions (10s), chat history (3s while open)
- [ ] **Per-view polling intervals** aligned to spec: patients 30s, caregivers 60s, org 300s, scheduling tasks 15s
- [ ] **`useNotifications` hook** (10s poll, feeds TopBar badge)

## 9) Verification + E2E Gaps

- [x] Integration tests: patient update pipeline, file ingest, detect fan-out
- [x] Domain detection unit tests: health, appointment, grocery, financial
- [x] Scheduling E2E tests (14 tests covering full lifecycle including cancel)
- [x] Dashboard E2E tests (Playwright, all four views)
- [x] Overdue dedup notification tests (10 tests for expiration loop)
- [ ] **Fix 4 pre-existing test failures** (see CONTEXT.md §2.3): `test_api.py` (2), `test_detection_life_graph_context.py` (1), `test_mock_api_coverage.py` isolation (1)

## 10) Documentation + Delivery Gaps

- [x] README updated with full spec-aligned feature set and API contract
- [x] `docs/architecture.md` — pipeline diagrams and payload contracts
- [x] `docs/demo-checklist.md` — 9 demo scenarios with validation steps
