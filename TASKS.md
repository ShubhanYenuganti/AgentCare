# TASKS — Remaining Features vs `MACOS_build_spec_v7_final.md`

Last audited: 2026-04-25  
Audit basis: `MACOS_build_spec_v7_final.md` compared against current code in `agents/`, `api/`, `data/`, and `dashboard/`.

## Snapshot

- Sprint 1 foundation complete.
- Sprint 2 data-layer + executor core complete (sections 1 and most of 2 done). Remaining Sprint 2 work: action-chat pipeline, full intent handler surface.
- Sprint 3–11 contain major remaining work, especially deterministic domain logic, patient update pipeline, scheduling workflow, and full dashboard UX.

## 1) Data Layer + Seed Gaps

- [x] Add missing life-graph tables to `data/schema.sql`: `emergency_contacts`, `medications`, `caregiver_notes`, `appointments`, `grocery`, `grocery_staples`, `financial_bills`, `financial_anomalies`.
- [x] Expand `action_history` schema to include remaining spec fields: `completion_date`, `assigned_caregiver`, `caregiver_options_json`, `outcome`.
- [x] Align `expiration_notifications` columns to include explicit `notified_at` semantics from spec.
- [x] Update `agents/shared/db.py` serialization to build spec-style full life graph from normalized tables (not only patient JSON blob + linked tables).
- [x] Add DB helper(s) needed for scheduling chat-selection flow (for example latest pending scheduling action retrieval by requester/session, not global heuristic).
- [x] Extend `data/seed.py` to populate new normalized domain tables with deterministic baseline data used by spec checks.
- [x] Seed data that supports all domain detection checks (appointments cadence, grocery staples/delivery cadence, bill due/autopay/anomaly history).

## 2) Executor + Internal Detection Pipeline Gaps

- [x] Implement executor internal endpoint `POST /internal/detect` (spec trigger path used by ingest + patient-update confirm).
- [x] Implement explicit `run_detection(patient_id, trigger, updated_domain)` flow callable from FastAPI/internal HTTP.
- [x] Inject domain-specific org context into each fan-out message using `ORG_CONTEXT_MAP` from DB org profile (currently fan-out sends empty org context).
- [x] Implement spec expiration loop behavior on executor (`@on_interval(900)`): fetch overdue actions, mark overdue, dedupe notifications, write dashboard notifications, optional ASI:One push.
- [x] Add scheduling-task post-processing in executor supervisor-result handler to set `scheduling_status="pending_approval"` for new scheduling tasks.
- [ ] Implement action-chat processing endpoint/path (`/process-action-chat` equivalent) for API `POST /actions/{id}/chat`.
- [ ] Align intent handler surface with spec workflow: onboarding, scheduling query handling, action-bound modification/question handling, and general query fallback with DB-backed context.

## 3) Ingest + Patient Update Pipeline Gaps

- [ ] Replace current `/ingest/text` proxy behavior with spec extraction flow: LLM extraction -> `write_patient()` -> immediate `internal/detect` trigger (`patient_create`).
- [ ] Add `POST /ingest/file` with PDF extraction (`pdfplumber`) and image extraction (`call_claude_vision`) as defined in spec.
- [ ] Implement `POST /patients/{id}/update` with classifier output: `domain`, `operation`, `fields_changed`, `summary`, `proposed_changes`.
- [ ] Persist proposed changes in update records and return confirmation payload (`requires_confirmation=true`).
- [ ] Implement `POST /patients/{id}/update/{update_id}/confirm` to apply staged changes and trigger `internal/detect` with `patient_update`.
- [ ] Implement `POST /patients/{id}/update/file` using same staged-confirmation flow.
- [ ] Implement `GET /patients/{id}/update-history`.
- [ ] Ensure removal operations are soft-delete (`active=0`) across all normalized life-graph tables.

## 4) Domain Supervisor/Worker Logic Gaps

### Health domain

- [ ] Replace generic detection generation with explicit spec checks: refill due, missed-dose+worsening, OpenFDA interaction, OpenFDA recall.
- [ ] Implement OpenFDA live integration calls for interaction + recall checks with robust timeout/retry/fallback behavior.
- [ ] Add supervisor risk-scoring pass (LLM reassessment for urgency/framing/instruction), with urgency override and `review_by` recalculation.
- [ ] Implement health modification pipeline parity with spec: live-data aware revision path, review pass, retry pass, and changes summary policy.
- [ ] Implement question pipeline live-API branching (`question_requires_live_api`) per spec.

### Appointment domain

- [ ] Replace generic LLM-only detection with explicit checks: overdue appointment, transport planning (Google Maps Distance Matrix), visit prep, post-visit extraction workflow.
- [ ] Add Google Maps integration path for transport planning and scheduling-task draft generation payload.
- [ ] Enforce scheduling-task output structure (`manual_action_type`, scheduling metadata) matching spec.

### Grocery domain

- [ ] Replace generic detection with explicit checks: delivery staleness, dietary conflict, supply reorder.
- [ ] Ensure staleness/supply checks call cart/order mock APIs in deterministic rule path (not only suggested by LLM).
- [ ] Normalize grocery actions to spec scheduling-task behavior where applicable.

### Financial domain

- [ ] Replace generic detection with explicit checks: bill due alert, missed autopay, anomaly detection.
- [ ] Add anomaly pass using defined comparison policy from life-graph financial history.

### Cross-domain supervisor behavior

- [ ] Enforce spec rule: non-health domains should not support modification handlers; return "not supported yet" behavior for those domains.
- [ ] Maintain Q&A support across all four domains with optional live API worker call path based on query freshness keywords.

## 5) Scheduling Agent + Scheduling API Gaps

- [ ] Replace scheduling-agent mock-only `MockDomainTask` handler with `SchedulingQuery` flow defined in spec.
- [ ] Implement scheduling options generation via `/mock/caregivers/available`, persist options on action, send numbered options to requester.
- [ ] Add scheduling chat-selection handler (numeric choice/cancel), assign caregiver, book slot, write notification, set `scheduling_status="unconfirmed"`.
- [ ] Implement scheduling router endpoints from spec: `POST /scheduling/{id}/assign`, `POST /scheduling/{id}/confirm`, `POST /scheduling/{id}/decline`.
- [ ] Ensure decline flow frees slot, resets scheduling status, clears assignment, and writes escalation notification.

## 6) FastAPI Contract Gaps

- [ ] Add CORS middleware behavior described in spec for dashboard origin(s).
- [ ] Expand `GET /patients` response to include urgency summary, pending counts, overdue counts, and assigned caregiver summaries.
- [ ] Expand `GET /patients/{id}` response to include full life graph + `pending_actions` + `action_history`.
- [ ] Expand `GET /actions` filtering contract (`domain`, `urgency`, `type`, `patient_id`, `is_overdue`) and response enrichment fields.
- [ ] Add `POST /actions/{id}/dismiss`.
- [ ] Add `POST /actions/{id}/chat`.
- [ ] Add `GET /actions/{id}/chat-history`.
- [ ] Expand caregiver router with `GET /caregivers/{id}/schedule` and `GET /caregivers/{id}/assignments`.
- [ ] Align org router method semantics with spec (`PUT` support alongside/over `PATCH`).
- [ ] Ensure approve path writes spec completion metadata (`completion_date`, `outcome`) in addition to reviewed/completed flags.

## 7) Mock API Parity Gaps

- [ ] Align mock route payload/response contracts to spec snapshots where intentionally required (notably Amazon reorder response semantics).
- [ ] Keep caregiver-availability SQL behavior fully aligned to spec sort/fallback policy (assigned first, then start time; next 3 business days fallback).
- [ ] Add coverage tests asserting stable response envelopes for all mock endpoints used by detection and approval flows.

## 8) Dashboard Implementation Gaps (Major)

### View 1 — Action Feed

- [ ] Build spec component architecture (`AppShell`, `TopBar`, `NavTabs`, `ActionFeed`, stateful `ActionCard` variants, `ActionChatPanel`, `DraftModal`, `Banner`, `Toast`).
- [ ] Implement health modify flow UI and non-health Q&A flow UI parity.
- [ ] Implement action card lifecycle visuals: overdue/tier banners, modification in-progress lock, draft version badge, update flash state.
- [ ] Implement scheduling-card deep-link behavior to caregiver view.

### View 2 — Patient Roster

- [ ] Build split layout with patient sidebar, patient detail sections, warning links to actions.
- [ ] Add add/update patient workflows including staged confirmation state machine and file upload path.
- [ ] Add update-history rendering from backend endpoint.

### View 3 — Caregiver Management

- [ ] Build scheduling strip/panel with pending tasks and assignment controls.
- [ ] Build caregiver detail, 14-day schedule grid, assignment list, confirm/decline flows.
- [ ] Implement deep-link preselect behavior from Action Feed.

### View 4 — Org Dashboard

- [ ] Build org summary, protocol panels, caregiver roster, org metrics cards.
- [ ] Add polling hooks and proper typed API client layer (`src/api/client.ts`, `src/types/index.ts`, hooks set).

## 9) Verification + E2E Gaps

- [ ] Add integration tests for patient update submit/confirm/file flows and detection trigger side effects.
- [ ] Add executor internal detect endpoint tests and fan-out behavior tests for create/update triggers.
- [ ] Add domain-specific deterministic detection tests (health + appointment + grocery + financial expected outputs).
- [ ] Add scheduling agent end-to-end selection tests (query -> options -> numeric select -> status transition).
- [ ] Add dashboard E2E tests for all four views and critical UX state transitions from spec.
- [ ] Add overdue dedup notification tests for expiration loop (`dashboard` and `asi_one` channel dedupe).

## 10) Documentation + Delivery Gaps

- [ ] Update README to match current runtime and full spec-aligned feature set once implemented.
- [ ] Add architecture + pipeline docs reflecting internal detect, patient update staging, scheduling lifecycle, and API payload contracts.
- [ ] Add demo-run validation checklist aligned with Section 16 scenario steps.
