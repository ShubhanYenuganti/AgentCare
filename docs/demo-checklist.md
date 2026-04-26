# MACOS Demo Validation Checklist

Aligned with Section 16 (Demo Scenarios) of `MACOS_build_spec_v7_final.md`.

## Prerequisites

- [x] Backend running: `python -m uvicorn api.main:app --host 0.0.0.0 --port 8000`
- [x] Dashboard running: `npm run dev` (opens on http://localhost:5173)
- [x] DB seeded: `python data/seed.py`
- [x] (Optional) Full agent stack: `python -m agents.run_all`

---

## Scenario 1: Action Feed Load and Urgency Display

- [x] Navigate to `/actions`
- [x] Action cards load within 3 seconds
- [x] Cards sorted by urgency score (tier_1 / tier_0 at top)
- [x] At least one overdue action shows red **OVERDUE** banner
- [x] Urgency tier badges visible: red (tier_1), amber (tier_2), green (tier_3)
- [x] Cards auto-refresh every 10 seconds (verify via network tab)

## Scenario 2: Health Domain — Chat and Draft Modification

- [ ] Click **Ask** on a non-health-modify action card
- [ ] Chat panel slides open from the right
- [ ] Type a message and click **Send**
- [ ] Message appears in chat history
- [ ] Chat history polls every 3 seconds (new assistant reply appears without refresh)
- [ ] Click **Modify Draft** on a health domain card with draft content
- [ ] DraftModal opens showing current `draft_content`
- [ ] Enter a modification instruction
- [ ] Click **Submit** — PATCH request sent with `modification_instruction` + `idempotency_key`
- [ ] Card shows **Modification in progress…** with disabled button while processing

## Scenario 3: Patient Roster — Add and View Patient

- [ ] Navigate to `/patients`
- [ ] Patient list loads in sidebar with names, pending count, urgency pill
- [ ] Click a patient — detail panel loads within 2 seconds
- [ ] Life graph sections visible: Health, Appointments, Grocery, Financial, Emergency Contacts
- [ ] Pending actions list and action history accordion visible
- [ ] Click **+ Add** → Add Patient modal opens
- [ ] **Text Ingest tab**: enter free-form patient text → click **Add Patient**
- [ ] Modal closes and roster refreshes with new patient
- [ ] **File Upload tab**: upload a PDF or image → roster refreshes

## Scenario 4: Patient Update — Staged Confirmation

- [ ] Select a patient in the Patient Roster
- [ ] Click **Update** tab
- [ ] Enter update text (e.g., "Change medication to 20mg Lisinopril")
- [ ] Click **Submit Update**
- [ ] Proposed changes panel appears (awaiting_confirmation state)
- [ ] Click **Confirm** → update applied, patient detail refreshes
- [ ] Click **Update History** tab → submitted update appears in history

## Scenario 5: Caregiver Management — Scheduling Flow

- [ ] Navigate to `/caregivers`
- [ ] Scheduling strip shows actions in `pending_approval` or `unconfirmed` status
- [ ] Select a caregiver from the assignment dropdown on a `pending_approval` action
- [ ] Action moves to `unconfirmed` status
- [ ] **Confirm** button appears
- [ ] Click **Confirm** → action status updates to `confirmed`
- [ ] Select a different `unconfirmed` action
- [ ] Click **Decline** → action resets to `pending_approval`, caregiver cleared
- [ ] Select a caregiver from the caregiver list
- [ ] 14-day schedule grid renders with booked/available slots
- [ ] Assignment list shows current assignments

## Scenario 6: Deep-Link from Action Feed to Caregiver Management

- [ ] Navigate to `/actions`
- [ ] Find an action card with **View Scheduling** button
- [ ] Click **View Scheduling**
- [ ] Navigates to `/caregivers`
- [ ] The corresponding scheduling action row is highlighted (purple border)

## Scenario 7: Org Dashboard

- [ ] Navigate to `/org`
- [ ] Org name, care philosophy displayed in summary panel
- [ ] Protocol count, caregiver count, patient count shown
- [ ] Four metric cards visible: Pending Actions, Overdue Actions, 30-Day Completion, Avg Urgency
- [ ] Protocol cards render (one per protocol in org profile)
- [ ] Caregiver roster table shows all caregivers
- [ ] Click **Edit Org Profile** → modal opens with pre-filled fields
- [ ] Update org name → click **Save**
- [ ] Summary panel refreshes with updated org name

## Scenario 8: Overdue Action Lifecycle

- [ ] Identify an action with `review_by` in the past and `completed=0`
- [ ] Verify `is_overdue=1` in DB: `sqlite3 data/life_graph.db "select action_id, is_overdue from action_history where is_overdue=1"`
- [ ] Verify `urgency_level=tier_0` for overdue actions
- [ ] Verify `expiration_notifications` table has one entry per channel per action:
  ```sql
  SELECT action_id, channel, COUNT(*) FROM expiration_notifications GROUP BY action_id, channel;
  ```
  Expected: COUNT=1 for each (action_id, channel) pair

## Scenario 9: Run Automated Tests

```bash
# Backend integration + unit tests
pytest tests/ -v --tb=short

# Domain detection tests
pytest tests/test_health_detection.py tests/test_appointment_detection.py \
       tests/test_grocery_detection.py tests/test_financial_detection.py -v

# Scheduling E2E
pytest tests/test_scheduling_e2e.py -v

# Expiration loop tests
pytest tests/test_expiration_loop.py -v

# Dashboard E2E (requires backend + dashboard running)
npx playwright test --project=chromium
```

Expected: all tests pass.

## Sign-off

- [ ] All 7 demo scenarios completed successfully
- [ ] All test suites passing
- [ ] No JS console errors in dashboard
- [ ] No unhandled API errors in backend logs
