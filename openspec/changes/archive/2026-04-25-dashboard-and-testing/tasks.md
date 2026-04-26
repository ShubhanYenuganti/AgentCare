## 1. Dashboard project setup

- [x] 1.1 Add RTK Query (`@reduxjs/toolkit`, `react-redux`) to `dashboard/package.json`
- [x] 1.2 Add Playwright (`@playwright/test`) to `dashboard/package.json` as a dev dependency
- [x] 1.3 Create `dashboard/src/types/index.ts` with TypeScript interfaces: `Patient`, `LifeGraph`, `Action`, `ChatMessage`, `Caregiver`, `OrgProfile`, `SchedulingOption`
- [x] 1.4 Create `dashboard/src/api/client.ts` — RTK Query API slice with endpoints for all FastAPI routes: patients, actions, caregivers, org, scheduling, chat

## 2. AppShell and navigation

- [x] 2.1 Create `dashboard/src/components/AppShell.tsx` with `TopBar` and `NavTabs` (Action Feed, Patients, Caregivers, Org)
- [x] 2.2 Set up React Router with four lazy-loaded view routes; update `dashboard/src/main.tsx` to mount AppShell
- [x] 2.3 Add polling hooks to RTK Query client: `GET /actions` polls every 10s when Action Feed is mounted

## 3. Action Feed view

- [x] 3.1 Create `dashboard/src/views/ActionFeed.tsx` — fetches actions via RTK Query hook, renders list of `ActionCard` components
- [x] 3.2 Create `dashboard/src/components/ActionCard.tsx` — polymorphic card with three variants: health-modify (Modify Draft button), non-health Q&A (Ask button), scheduling (View Scheduling deep-link button)
- [x] 3.3 Add overdue banner to `ActionCard`: display red "OVERDUE" banner when `is_overdue=true`
- [x] 3.4 Add urgency tier banner to `ActionCard`: high=red, medium=amber, low=green border/badge
- [x] 3.5 Add modification-in-progress lock state to `ActionCard`: disable Modify Draft button when `modification_in_progress=1`
- [x] 3.6 Create `dashboard/src/components/ActionChatPanel.tsx` — slide-over drawer, sends `POST /actions/{id}/chat`, polls `GET /actions/{id}/chat-history` every 3s while open
- [x] 3.7 Create `dashboard/src/components/DraftModal.tsx` — displays `draft_content`, allows inline edit, submits `PATCH /actions/{id}` with `modification_instruction` and fresh `idempotency_key`

## 4. Patient Roster view

- [x] 4.1 Create `dashboard/src/views/PatientRoster.tsx` — two-column split layout with sidebar patient list and detail panel
- [x] 4.2 Patient sidebar renders each patient with `pending_action_count` and `highest_urgency_level` pill from enriched API response
- [x] 4.3 Patient detail panel renders full life graph sections (health, appointments, grocery, financial, emergency contacts)
- [x] 4.4 Patient detail panel includes `pending_actions` summary list and `action_history` accordion
- [x] 4.5 Add "Add Patient" button that opens a modal with two tabs: text ingest (`POST /ingest/text`) and file upload ingest (`POST /ingest/file`)
- [x] 4.6 Implement staged confirmation state machine for patient updates: `idle → submitting → awaiting_confirmation → confirmed | cancelled`; submit via `POST /patients/{id}/update`, confirm via `POST /patients/{id}/update/{uid}/confirm`
- [x] 4.7 Add "Update History" tab to patient detail panel fetching `GET /patients/{id}/update-history`

## 5. Caregiver Management view

- [x] 5.1 Create `dashboard/src/views/CaregiverManagement.tsx` — scheduling strip on the left, caregiver detail panel on the right
- [x] 5.2 Scheduling strip lists all actions with `scheduling_status` in `["pending_approval", "unconfirmed"]` with caregiver assignment dropdowns (calls `POST /scheduling/{id}/assign`)
- [x] 5.3 Caregiver detail panel renders 14-day schedule grid from `GET /caregivers/{id}/schedule`
- [x] 5.4 Caregiver detail panel renders assignment list from `GET /caregivers/{id}/assignments`
- [x] 5.5 Add Confirm and Decline buttons on unconfirmed scheduling actions; wire to `POST /scheduling/{id}/confirm` and `POST /scheduling/{id}/decline`
- [x] 5.6 Implement deep-link preselect: when navigated from an ActionCard scheduling button, highlight the relevant action row in the scheduling strip using router state

## 6. Org Dashboard view

- [x] 6.1 Create `dashboard/src/views/OrgDashboard.tsx` — org summary panel, protocol cards, metrics cards, caregiver roster table
- [x] 6.2 Org summary panel fetches `GET /org` and displays org name, protocol count, active caregiver count, total patient count
- [x] 6.3 Render one protocol card per protocol in the org profile with name, description, and domain tag
- [x] 6.4 Render four metric cards: total pending actions, total overdue actions, 30-day completion rate, average urgency score (computed client-side from `GET /actions` data)
- [x] 6.5 Add "Edit Org Profile" form that submits via `PUT /org` and refreshes the summary panel on success

## 7. Backend integration tests

- [x] 7.1 Create `tests/integration/test_patient_update_pipeline.py`: test submit → confirm flow asserts detection trigger fires and actions are written to DB
- [x] 7.2 Create `tests/integration/test_ingest_file.py`: test PDF ingest via `POST /ingest/file` asserts patient written and patient_create detection triggered
- [x] 7.3 Create `tests/integration/test_executor_detect.py`: test `POST /internal/detect` with `patient_create` triggers fan-out to all 4 domains; test `patient_update` with `updated_domain="health"` fans out to health only

## 8. Domain detection unit tests

- [x] 8.1 Create `tests/test_health_detection.py`: test refill due, missed dose, OpenFDA interaction (mocked), OpenFDA recall (mocked) rule checks against deterministic seed data
- [x] 8.2 Create `tests/test_appointment_detection.py`: test overdue appointment, transport planning (Maps key absent fallback), visit prep rule checks
- [x] 8.3 Create `tests/test_grocery_detection.py`: test delivery staleness, dietary conflict, supply reorder rule checks
- [x] 8.4 Create `tests/test_financial_detection.py`: test bill due alert, missed autopay, spending anomaly rule checks against deterministic seed financial history

## 9. Scheduling E2E tests

- [x] 9.1 Create `tests/test_scheduling_e2e.py`: test full scheduling query → options → numeric selection → `unconfirmed` status transition
- [x] 9.2 Add test for cancel flow: selection "cancel" → `scheduling_status="cancelled"` 
- [x] 9.3 Add REST API E2E tests: assign then confirm → `confirmed` + `completed=1`; decline → `pending_approval` + null caregiver

## 10. Dashboard E2E tests (Playwright)

- [x] 10.1 Create `dashboard/e2e/action-feed.spec.ts`: test initial load and urgency sort, overdue banner visible, chat panel send + history, draft modal submit
- [x] 10.2 Create `dashboard/e2e/patient-roster.spec.ts`: test patient selection loads detail, text ingest add patient, staged update confirmation flow, update history tab
- [x] 10.3 Create `dashboard/e2e/caregiver-management.spec.ts`: test scheduling strip load, confirm + decline flow, schedule grid render
- [x] 10.4 Create `dashboard/e2e/org-dashboard.spec.ts`: test org summary load, protocol panel render, org profile edit and refresh
- [x] 10.5 Add Playwright config at `dashboard/playwright.config.ts` with baseURL, test fixture for FastAPI server startup

## 11. Overdue notification tests

- [x] 11.1 Create `tests/test_expiration_loop.py`: test that running the expiration loop twice for the same overdue action writes exactly one `notification_log` entry per channel (`dashboard`, `asi_one`)
- [x] 11.2 Add test that the expiration loop marks actions with `review_by` in the past and `completed=0` as overdue

## 12. Documentation

- [x] 12.1 Update `README.md` to reflect current runtime: full spec-aligned feature set, all four domains, scheduling lifecycle, API contract
- [x] 12.2 Add `docs/architecture.md`: pipeline diagrams for internal detect, patient update staging, scheduling lifecycle, API payload contracts
- [x] 12.3 Add `docs/demo-checklist.md`: validation checklist aligned with Section 16 scenario steps from the build spec
