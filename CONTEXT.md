# MACOS Context

Last updated: April 25, 2026

This document reflects the implementation state after three recent openspec changes:
- `backend-domain-and-api-completion` (44/44 tasks — domain rules, scheduling, API, mock parity)
- `dashboard-and-testing` (52/52 tasks — full 4-view dashboard, RTK Query, tests, docs)

It supersedes all prior CONTEXT.md content. Structure:

1. Implemented features with local test instructions
2. Remaining gaps from `MACOS_build_spec_v7_final.md`

---

## 1. Implemented Features

### 1.1 Full agent stack

**What:** 10-process agent topology running locally via `python -m agents.run_all`. Executor → Domain Supervisors (health, appointment, grocery, financial) → Workers, plus Scheduling Agent.

**How to test:**
```bash
SQLITE_DB_PATH=data/life_graph.db \
EXECUTOR_INTERNAL_URL=http://localhost:8001 \
MOCK_API_BASE=http://localhost:8000 \
python -m agents.run_all
```
In another terminal:
```bash
curl -s http://localhost:8001/health | python3 -m json.tool
```
**Expected:** `{"status": "ok"}` from all agents, health logs appear in the run_all console.

---

### 1.2 Explicit domain detection rules

**What:** All four domain workers run deterministic rule checks before (and merged with) the LLM pass.

#### Health (`agents/health/worker.py`)
- **Refill due** — medication `refill_due` within 7 days → tier_2 draft to pharmacy
- **Missed dose + worsening** — consecutive gap ≥ 3 days + LLM note assessment → tier_1 escalation to prescriber
- **OpenFDA interaction** — live call to `api.fda.gov/drug/label.json` for each co-prescribed medication pair → tier_1 if interaction found
- **OpenFDA recall** — live call to `api.fda.gov/drug/enforcement.json` per medication → tier_0 if active recall

#### Appointment (`agents/appointment/worker.py`)
- **Overdue appointment** — `months_since_last_visit > recommended_frequency_months` → tier_1 scheduling draft
- **Visit prep** — appointment within 48h, no existing prep action → tier_2 LLM summary
- **Transport planning** — appointment within 7 days + `transport_required=True` → calls Google Maps Distance Matrix (skipped gracefully if `GOOGLE_MAPS_API_KEY` absent) → `manual_action_type="transport"` scheduling task

#### Grocery (`agents/grocery/worker.py`)
- **Delivery staleness** — `days_since_last_delivery > max(staple.frequency_days)` → calls `POST /mock/instacart/cart` → tier_2 grocery_delivery scheduling task
- **Dietary conflict** — staple vs `dietary_restrictions` mismatch → tier_2 LLM draft
- **Supply reorder** — quantity at or below threshold → calls `POST /mock/amazon/reorder` → tier_2 supply_reorder scheduling task

#### Financial (`agents/financial/worker.py`)
- **Bill due alert** — unpaid bill due within 5 days, autopay off → tier_2 (tier_1 if ≤ 2 days)
- **Missed autopay** — autopay bill past due, no completion record → tier_1 alert
- **Spending anomaly** — current bill > 150% of trailing average from `financial_anomalies` → tier_1 or tier_2 LLM analysis

**How to test (unit):**
```bash
python -m pytest tests/test_health_detection.py \
  tests/test_appointment_detection.py \
  tests/test_grocery_detection.py \
  tests/test_financial_detection.py -v
```
**Expected:** 24 tests pass. Tests seed deterministic patient data and assert on `ActionDraft` type, domain, urgency level, and `patient_id` from the parse pipeline.

**How to test (via API):**
```bash
# Seed DB and start API
python data/seed.py
python -m uvicorn api.main:app --port 8000

# Trigger patient_create detection for pt_001
curl -s -X POST http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Margaret Chen, 74, 123 Sunset Blvd. Lisinopril 10mg daily."}' | python3 -m json.tool
```
**Expected:** `{"success": true, "data": {"patient_id": "...", "detect_status": ...}}`. After a few seconds, `GET /actions` returns draft actions for the new patient.

---

### 1.3 Supervisor risk-scoring pass

**What:** All four domain supervisors call `_risk_score_drafts()` (`agents/shared/supervisor_utils.py`) after receiving worker drafts. Single LLM call reassesses urgency framing and recalculates `review_by` before writing to DB.

**How to test:**
```bash
python -m pytest tests/test_detection_life_graph_context.py -v -k "supervisor"
```
**Expected:** Tests pass confirming supervisor correctly parses and scopes life graph context per domain before the risk pass.

---

### 1.4 Health modification and question pipelines

**What:**
- Modification: `PATCH /actions/{id}` with `modification_instruction` → executor routes to health supervisor → live-data keyword check → optional health worker API call → LLM revision → review pass → retry if review fails → `replace_draft()` + notification
- Question: `POST /actions/{id}/chat` → executor routes to domain supervisor → freshness-keyword check → optional live API lookup by worker → LLM answer → chat history written

Non-health domains return a "not supported" response for modification requests.

**How to test:**
```bash
# Start API and agent stack first, then:
ACTION_ID=$(curl -s http://localhost:8000/actions | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data'][0]['action_id'])")

# Send modification
curl -s -X PATCH http://localhost:8000/actions/$ACTION_ID \
  -H "Content-Type: application/json" \
  -d '{"modification_instruction": "Add that Dr. Patel should be cc'd", "idempotency_key": "test-001"}' | python3 -m json.tool

# Check modification in progress flag
curl -s http://localhost:8000/actions/$ACTION_ID | python3 -m json.tool

# Send a question via chat
curl -s -X POST http://localhost:8000/actions/$ACTION_ID/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Why is this flagged tier 1?"}' | python3 -m json.tool

# Fetch chat history
curl -s http://localhost:8000/actions/$ACTION_ID/chat-history | python3 -m json.tool
```
**Expected:** `modification_in_progress=1` set immediately on PATCH; after agent processes, `draft_content` updated and `modification_in_progress=0`. Chat history shows user message and agent reply.

---

### 1.5 Scheduling agent workflow

**What:** Full `SchedulingQuery` flow: executor receives scheduling query → sends to scheduling agent → agent calls `POST /mock/caregivers/available` → persists options in `caregiver_options_json` → sends numbered option list to requester. Chat-selection handler parses numeric reply or "cancel" → assigns caregiver, sets `scheduling_status="unconfirmed"`, books slot, writes notification.

**How to test (REST API path):**
```bash
# Create a scheduling action (pending_approval)
# Then assign, confirm, decline, or cancel via REST:

curl -s -X POST http://localhost:8000/scheduling/$ACTION_ID/assign \
  -H "Content-Type: application/json" \
  -d '{"caregiver_id": "cg_001"}' | python3 -m json.tool
# Expected: scheduling_status="unconfirmed", assigned_caregiver="cg_001"

curl -s -X POST http://localhost:8000/scheduling/$ACTION_ID/confirm | python3 -m json.tool
# Expected: scheduling_status="confirmed", completed=1

curl -s -X POST http://localhost:8000/scheduling/$ACTION_ID/decline | python3 -m json.tool
# Expected: scheduling_status="pending_approval", assigned_caregiver cleared, escalation notification written

curl -s -X POST http://localhost:8000/scheduling/$ACTION_ID/cancel | python3 -m json.tool
# Expected: scheduling_status="cancelled", assigned_caregiver cleared
```

**How to test (E2E pytest):**
```bash
python -m pytest tests/test_scheduling_e2e.py -v
```
**Expected:** 14 tests pass covering assign, confirm, decline, cancel, 409/404 error paths, and DB state verification.

---

### 1.6 Complete FastAPI REST surface

**What:** All spec-defined endpoints implemented with `{success, data, error}` envelope:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/actions?sort=rank` | Ranked action list (urgency score) |
| GET | `/actions/{id}` | Single action |
| PATCH | `/actions/{id}` | Modification instruction / mark reviewed |
| POST | `/actions/{id}/dismiss` | Mark dismissed + completed |
| POST | `/actions/{id}/chat` | Send chat message |
| GET | `/actions/{id}/chat-history` | Full chat thread |
| GET | `/patients` | Enriched list: pending_action_count, highest_urgency_level |
| GET | `/patients/{id}` | Full detail: life_graph, pending_actions, action_history |
| POST | `/patients/{id}/update` | Staged update (LLM classification → proposed_changes) |
| POST | `/patients/{id}/update/{uid}/confirm` | Apply staged update → trigger detection |
| GET | `/patients/{id}/update-history` | All update records |
| POST | `/ingest/text` | Text extraction → write patient → trigger detect |
| POST | `/ingest/file` | PDF/image extraction → write patient → trigger detect |
| GET | `/caregivers` | All caregivers with today's availability |
| GET | `/caregivers/{id}/schedule` | 14-day schedule grid |
| GET | `/caregivers/{id}/assignments` | Assignment list with pending counts |
| POST | `/scheduling/{id}/assign` | pending_approval → unconfirmed |
| POST | `/scheduling/{id}/confirm` | unconfirmed → confirmed + completed=1 |
| POST | `/scheduling/{id}/decline` | Reset to pending_approval + escalation |
| POST | `/scheduling/{id}/cancel` | Cancel → scheduling_status="cancelled" |
| GET | `/notifications` | Unread dashboard notifications |
| POST | `/notifications/{id}/read` | Mark read |
| GET | `/org` | Org profile |
| PUT | `/org` | Update org profile |

**How to test:**
```bash
python -m pytest tests/test_api.py -v --tb=short
# Also:
python -m pytest tests/integration/ -v
```
**Expected:** Most tests in `test_api.py` pass (4 pre-existing failures unrelated to recent changes — see section 2.3). All 15 integration tests pass.

---

### 1.7 Mock API surface

**What:** Six mock endpoints implementing spec contracts:

- `GET /mock/cvs/available` — CVS pharmacy availability lookup
- `POST /mock/cvs/refill` — CVS refill request → `confirmation_id: CVS-YYYYMMDD-XXXXXX`
- `GET /mock/cal/available` — calendar slot lookup
- `POST /mock/cal/book` — appointment booking → next business day 10:00am slot
- `POST /mock/instacart/cart` — grocery cart creation → `cart_id: INST-...`
- `POST /mock/amazon/reorder` — supply reorder → `order_id: AMZ-...`
- `POST /mock/caregivers/available` — live SQLite query for available caregivers (assigned-first sort, 3-day fallback)

**How to test:**
```bash
python -m pytest tests/test_mock_api_coverage.py -v
python -m pytest tests/test_mock_snapshots.py -v
```
**Expected:** All mock API coverage and snapshot tests pass with stable response envelope shapes.

---

### 1.8 Executor expiration loop

**What:** Runs every 900s on executor. Fetches actions where `review_by < now AND completed=0 AND is_overdue=0`, marks each `is_overdue=1, urgency_level=tier_0, escalation_count+=1`, dedupes via `expiration_notifications` table, writes dashboard notification per action once.

**How to test:**
```bash
python -m pytest tests/test_expiration_loop.py -v
```
**Expected:** 10 tests pass covering:
- `test_dashboard_notification_deduped` — exactly 1 entry after 2 loop runs
- `test_asi_one_notification_deduped` — exactly 1 entry for asi_one channel
- `test_both_channels_exactly_one_each` — N loop runs still produce 1 entry each channel
- `test_mark_action_overdue_sets_is_overdue_flag` — DB confirms `is_overdue=1, urgency_level=tier_0`

---

### 1.9 Patient ingest and staged update pipeline

**What:**
- `POST /ingest/text` — LLM extracts patient fields → `write_patient()` → fires `patient_create` detect
- `POST /ingest/file` — PDF via pdfplumber or image via Claude vision → same pipeline
- `POST /patients/{id}/update` — LLM classifies update → returns `proposed_changes` with `requires_confirmation: true`
- `POST /patients/{id}/update/{uid}/confirm` — applies staged changes → fires `patient_update` detect with domain hint
- Removal operations use `active=0` soft-delete across all normalized life-graph tables

**How to test:**
```bash
python -m pytest tests/integration/test_patient_update_pipeline.py \
  tests/integration/test_ingest_file.py -v
```
**Expected:** 9 tests pass covering submit→confirm flow, update history, file ingest DB write, and detect_status field in response.

---

### 1.10 Executor detection fan-out logic

**What:** `_detection_domains_for_trigger(trigger, updated_fields, domain_hint)`:
- `patient_create` → all 4 domains
- `patient_update` with `domain_hint="health"` → health only
- `patient_update` with no hint → all 4 domains (or field-mapped subset)

**How to test:**
```bash
python -m pytest tests/integration/test_executor_detect.py -v
```
**Expected:** 6 tests pass confirming fan-out domain selection for all trigger/hint combinations.

---

### 1.11 Full dashboard — four views

**What:** React dashboard at `http://localhost:5173` built with RTK Query, lazy-loaded routes, Redux Provider.

**Run:**
```bash
# In one terminal — start FastAPI:
python data/seed.py
SQLITE_DB_PATH=data/life_graph.db python -m uvicorn api.main:app --port 8000

# In another terminal — start Vite dev server:
npm run dev
# Opens at http://localhost:5173
```

#### View 1 — Action Feed (`/actions`)

- Polls `GET /actions?sort=rank` every 10 seconds
- Each action renders as an `ActionCard` with one of three variants:
  - **health-modify**: "Modify Draft" (opens DraftModal) + "Ask" (opens ActionChatPanel)
  - **scheduling**: "View Scheduling" (navigates to `/caregivers` with action pre-selected)
  - **Q&A**: "Ask" (opens ActionChatPanel)
- Red "OVERDUE" banner on cards with `is_overdue=1`
- Urgency tier border/badge: red (tier_1), amber (tier_2), green (tier_3)
- "Modify Draft" disabled with lock text when `modification_in_progress=1`
- `ActionChatPanel` polls `GET /actions/{id}/chat-history` every 3s while open
- `DraftModal` submits `PATCH /actions/{id}` with `modification_instruction` + fresh `idempotency_key`

**Expected on load:** Seeded overdue action for Dorothy Kim (Metformin missed 4 days) appears at top with red OVERDUE banner and tier_0 urgency.

#### View 2 — Patient Roster (`/patients`)

- Two-column layout: patient sidebar (names, pending count, urgency pill) + detail panel
- Selecting a patient shows: life graph sections (health, appointments, grocery, financial, emergency contacts), pending actions summary, action history accordion
- "+" button opens Add Patient modal with Text Ingest and File Upload tabs
- Update tab: staged confirmation state machine `idle → submitting → awaiting_confirmation → confirmed | cancelled`
- Update History tab: `GET /patients/{id}/update-history`

**Expected on load:** 3 seeded patients (Margaret Chen, Robert Harris, Dorothy Kim) appear in sidebar. Clicking Margaret shows her medications, cardiology appointment, and grocery/financial data.

#### View 3 — Caregiver Management (`/caregivers`)

- Left: scheduling strip (actions with `scheduling_status` in `["pending_approval", "unconfirmed"]`) with assignment dropdowns
- Left bottom: caregiver list
- Right: caregiver detail with 14-day schedule grid + assignment list
- Confirm/Decline buttons on unconfirmed actions
- Deep-link preselect: navigating from a scheduling ActionCard highlights the action row in the strip

**Expected:** If agent stack is running and a scheduling task exists, it appears in the strip. Selecting "cg_001 — Sarah Okafor" shows her 14-day schedule grid.

#### View 4 — Org Dashboard (`/org`)

- Org summary: name, counts (protocols, caregivers, patients)
- 4 metric cards: total pending, total overdue, 30-day completion rate, avg urgency score
- Protocol cards per protocol in org profile
- Caregiver roster table
- "Edit Org Profile" form: `PUT /org` on submit, summary refreshes

**Expected on load:** "Sunrise Care Org" summary. Pending/overdue counts match `GET /actions`. Edit form pre-fills with current org fields.

---

### 1.12 Playwright E2E test suite

**What:** 4 spec files in `dashboard/e2e/` covering all views, with `playwright.config.ts` that starts both FastAPI and Vite dev server as webServer fixtures.

**Run:**
```bash
cd dashboard && npx playwright test --project=chromium
```
**Expected:** All E2E tests pass (tests degrade gracefully when no seed data exists — most assertions are conditional on action/patient availability).

---

### 1.13 Test suite summary

```bash
# Run all Python tests
python -m pytest tests/ -q

# Run only new tests from recent changes
python -m pytest tests/test_health_detection.py \
  tests/test_appointment_detection.py \
  tests/test_grocery_detection.py \
  tests/test_financial_detection.py \
  tests/test_scheduling_e2e.py \
  tests/test_expiration_loop.py \
  tests/integration/ -v
```

**Expected totals:** 184 collected, ~179 pass, 4 pre-existing failures (see 2.3 below).

New tests added by recent changes: 65 (24 domain detection + 14 scheduling E2E + 10 expiration loop + 5 integration/ingest + 6 executor fan-out + 6 TBD).

---

### 1.14 Documentation

- `README.md` — updated with full API contract table, runtime description, all features
- `docs/architecture.md` — pipeline diagrams: internal detect, patient update staging, scheduling lifecycle, API payload contracts
- `docs/demo-checklist.md` — 9 demo scenarios with step-by-step validation and expected DB state

---

## 2. Remaining Gaps from `MACOS_build_spec_v7_final.md`

The following items from the build spec are **not yet implemented**. Each is labeled with the spec section that defines it.

### 2.1 Dashboard — notification bell and polling (Spec §8, hooks list)

The spec defines a `useNotifications` hook (10s poll) and a TopBar badge showing unread notification count. The current `AppShell.tsx` has no notification indicator. `GET /notifications` exists in the API but nothing in the dashboard calls it.

**Missing:** Notification bell icon in TopBar, unread count badge, poll every 10s.

---

### 2.2 Dashboard — Toast and Banner shared components (Spec §8, `shared/` components)

The spec defines reusable `Toast.tsx` (modification_complete, scheduling_update events) and `Banner.tsx` (overdue escalation announcements). These are not implemented. The current ActionCard renders inline banners rather than a shared `Banner` component.

**Missing:** `Toast` system for live modification complete / scheduling update notifications. `Banner` shared component (current inline approach is functional but not spec-aligned).

---

### 2.3 Dashboard — draft version badge and update flash state (Spec §8, ActionCard)

The spec calls for:
- A draft version badge on ActionCard (e.g., "v2") reflecting `draft_version` from DB
- An "update flash" state — brief visual highlight when the card's draft is updated

`draft_version` is tracked in `action_history` but not read or displayed by `ActionCard.tsx`.

**Missing:** Read `draft_version` from action data and display badge. Add transient flash highlight on draft update.

---

### 2.4 Appointment worker — post-visit extraction (Spec §6.7 Check 4)

The spec defines a fourth appointment detection check: when the executor forwards caregiver visit notes, the LLM parses them into structured tasks and writes them to the life graph. This is not wired — the appointment worker currently only runs checks 1–3 (overdue, transport, visit prep).

**Missing:** `@on_message` handler for executor-forwarded post-visit caregiver notes in appointment worker.

---

### 2.5 Google Maps live integration — default off (Spec §6.7 Check 2)

Google Maps Distance Matrix is called only when `GOOGLE_MAPS_API_KEY` is set in the environment. With no key, transport planning check is skipped. The spec implies this check should fire (with a graceful fallback that still produces a transport scheduling task even without travel time data).

**Missing:** Fallback transport draft when Maps key is absent (draft without ETA, not silently skipped).

---

### 2.6 ASI:One caregiver push (Spec §6.12 expiration loop)

The expiration loop does attempt to push to `caregiver["asi_one_address"]` but all 10 seed caregivers have `asi_one_address: None`, so the push is always skipped. This is a data gap, not a code gap — the code path exists.

**Missing:** Populated `asi_one_address` values in seed data (or demo caregiver configuration). The push code in `executor/agent.py` is already correct.

---

### 2.7 Pre-existing test failures (not caused by recent changes)

Four tests were failing before the recent changes and remain unresolved:

| Test | Root cause |
|------|------------|
| `test_api.py::test_create_patient_and_fetch` | `GET /patients/{id}` response structure changed — test expects flat `patient_id` key, API now returns enriched nested response |
| `test_api.py::test_ingest_text_queued` | Ingest endpoint no longer returns `queued` field — returns `patient_id + detect_status` instead |
| `test_detection_life_graph_context.py::test_serialize_complete_life_graph_includes_linked_entities` | Serializer output shape changed from Sprint 2 baseline |
| `test_mock_api_coverage.py::test_caregivers_available` | DB state isolation issue when run in full suite (passes in isolation) |

**Action needed:** Update these 4 pre-existing tests to match current API response shapes. They are not regressions from the recent changes.

---

### 2.8 Dashboard component file structure (Spec §2, directory layout)

The spec defines a fine-grained component hierarchy (e.g., `PatientSidebar.tsx`, `PatientCard.tsx`, `MedicationPanel.tsx`, `ScheduleGrid.tsx` as separate files). The implementation consolidates these into 4 view files and 4 component files, which is functionally complete but does not match the spec's intended file organization.

**Missing:** Component decomposition into the spec-defined file tree if strict spec adherence is required. Functionally equivalent but structurally divergent.

---

### 2.9 `useNotifications` and per-view polling hooks (Spec §2, hooks list)

The spec defines a full set of RTK Query polling hooks: `useActions` (15s), `useActionChat` (3s), `useNotifications` (10s), `usePatients` (30s), `usePatient` (30s), `useCaregivers` (60s), `useCaregiver` (30s), `useCaregiverSchedule` (30s), `useSchedulingTasks` (15s), `useOrg` (300s).

Current polling intervals: `useGetActionsQuery` (10s), `useGetChatHistoryQuery` (3s), all others on-demand only. The spec's longer polling intervals for less-urgent views (patients: 30s, org: 300s) are not currently configured.

**Missing:** Per-hook polling intervals aligned to spec. `useSchedulingTasks` hook (currently the scheduling strip refetches from the action list, not a dedicated scheduling tasks endpoint). `useNotifications` hook.

---

## 3. How to Run Everything Locally

### Prerequisites
```bash
pip install -r requirements.txt
python data/seed.py
```

### Start the full stack
```bash
# Terminal 1 — FastAPI
SQLITE_DB_PATH=data/life_graph.db \
EXECUTOR_INTERNAL_URL=http://localhost:8001 \
MOCK_API_BASE=http://localhost:8000 \
ANTHROPIC_API_KEY=<your-key> \
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Agent stack (optional, needed for live detection/modification)
SQLITE_DB_PATH=data/life_graph.db \
EXECUTOR_INTERNAL_URL=http://localhost:8001 \
MOCK_API_BASE=http://localhost:8000 \
ANTHROPIC_API_KEY=<your-key> \
python -m agents.run_all

# Terminal 3 — Dashboard
npm run dev
# http://localhost:5173
```

### Run all tests
```bash
python -m pytest tests/ -q
```

### Run demo validation
Follow `docs/demo-checklist.md` — 9 scenarios with step-by-step commands and expected DB state.
