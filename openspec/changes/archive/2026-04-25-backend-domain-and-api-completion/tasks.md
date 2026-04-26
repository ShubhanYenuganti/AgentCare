## 1. Soft-delete and data layer cleanup

- [x] 1.1 Add `active` column guard to all removal operations in `agents/shared/db.py` — update delete helpers for medications, appointments, grocery, grocery_staples, financial_bills, financial_anomalies, caregiver_notes to use `UPDATE … SET active=0` instead of DELETE
- [x] 1.2 Verify all read helpers in `agents/shared/db.py` filter `WHERE active=1` for the normalized life-graph tables

## 2. Health domain detection rules

- [x] 2.1 Add `agents/domains/health/openfda.py` — thin sync wrapper for OpenFDA drug interaction API with 2s timeout and fallback dict on failure
- [x] 2.2 Add recall check to `openfda.py` — call OpenFDA recall endpoint per medication, return recall record or None
- [x] 2.3 Rewrite health worker detection to run explicit rule checks first: refill due (7-day window), missed dose + worsening note (48h), OpenFDA interaction, OpenFDA recall
- [x] 2.4 Keep secondary LLM pass in health worker for edge-case drafts; merge rule-triggered drafts with LLM drafts (dedupe by type)

## 3. Appointment domain detection rules

- [x] 3.1 Rewrite appointment worker to run explicit rule checks: overdue appointment (scheduled_date in past, completed=0), visit prep (within 48h, no existing prep action)
- [x] 3.2 Add `agents/domains/appointment/gmaps.py` — thin sync wrapper for Google Maps Distance Matrix API; skip gracefully if API key absent
- [x] 3.3 Wire transport planning rule check into appointment worker: call gmaps wrapper for transport_required appointments, embed ETA in draft_content, set manual_action_type="transport"
- [x] 3.4 Enforce scheduling-task output structure on all appointment scheduling drafts (manual_action_type, review_by, recipient_type, recipient_email all non-null)

## 4. Grocery domain detection rules

- [x] 4.1 Rewrite grocery worker to run explicit rule checks: delivery staleness (7-day threshold, call POST /mock/grocery/order), dietary conflict (staple vs restriction), supply reorder (quantity <= reorder_threshold)
- [x] 4.2 Ensure mock API calls in grocery worker use deterministic rule path — do not rely on LLM to suggest whether to call the API

## 5. Financial domain detection rules

- [x] 5.1 Rewrite financial worker to run explicit rule checks: bill due alert (5-day window, urgency escalation at 2 days), missed autopay (autopay_enabled=1, past due, paid=0), spending anomaly (current month > 150% of trailing 3-month average)
- [x] 5.2 Pull trailing 3-month average from `financial_anomalies` history table for the anomaly check

## 6. Domain supervisor risk-scoring pass

- [x] 6.1 Add `_risk_score_drafts(drafts, patient_snapshot, org_context)` helper in `agents/shared/supervisor_utils.py` (new file) — single `call_claude_json` call to reassess urgency framing and recalculate review_by
- [x] 6.2 Wire `_risk_score_drafts` into all four domain supervisors after workers return, before writing actions to DB

## 7. Health modification and question pipelines

- [x] 7.1 Update health supervisor to set `requires_live_api=True` on `ModificationTask` when modification instruction contains live-data keywords; else False
- [x] 7.2 Update health worker to call the relevant mock API when `requires_live_api=True` and incorporate response into `revised_draft`
- [x] 7.3 Add review pass in health supervisor: after receiving `ModificationDraft`, make one LLM call to review and optionally retry before returning `ModificationResult` with `changes_summary`
- [x] 7.4 Implement `question_requires_live_api` branching in all four domain supervisors: check freshness keywords, set `api_lookup_instruction` on `QuestionTask` accordingly
- [x] 7.5 Update all four domain workers to call the relevant mock API when `api_lookup_instruction` is non-null and include the API response in `QuestionApiResult`

## 8. Non-health modification guard

- [x] 8.1 Add `ModificationRequest` handler to appointment, grocery, and financial supervisors that immediately returns `ModificationResult(revised_draft="not_supported", changes_summary="Modification not supported for this domain")` without delegating to a worker

## 9. Scheduling agent workflow

- [x] 9.1 Add `@agent.on_message(SchedulingQuery)` handler to `agents/scheduling/agent.py`: call `GET /mock/caregivers/available`, persist options in `caregiver_options_json`, set `scheduling_status="pending_approval"`, send `SchedulingOptions` to requester
- [x] 9.2 Add chat-selection handler in scheduling agent: parse numeric choice or "cancel" from incoming message, match to pending options session, call `POST /mock/caregivers/book` on selection, set `scheduling_status="unconfirmed"`, write notification
- [x] 9.3 Add decline flow in scheduling agent: call `POST /mock/caregivers/release`, clear `assigned_caregiver`, reset `scheduling_status="pending_approval"`, write `ExpirationEscalation`
- [x] 9.4 Use `InMemoryRequestState` to track pending scheduling sessions keyed by `action_id`; stale entries cleared by existing 900s expiration loop

## 10. Scheduling API endpoints

- [x] 10.1 Add `POST /scheduling/{id}/assign` to `api/routers/scheduling.py` (create file): validate `scheduling_status="pending_approval"`, set `assigned_caregiver`, set `scheduling_status="unconfirmed"`, return updated action
- [x] 10.2 Add `POST /scheduling/{id}/confirm`: validate `scheduling_status="unconfirmed"`, set `scheduling_status="confirmed"`, `completed=1`, `completion_date`, write notification, return updated action
- [x] 10.3 Add `POST /scheduling/{id}/decline`: call mock release endpoint, clear `assigned_caregiver`, reset `scheduling_status="pending_approval"`, write escalation notification, return updated action
- [x] 10.4 Register scheduling router in `api/main.py`

## 11. FastAPI contract completion

- [x] 11.1 Add CORS middleware to `api/main.py` using `DASHBOARD_ORIGIN` env var (default `http://localhost:5173`)
- [x] 11.2 Update `GET /patients` in `api/routers/patients.py` to include `pending_action_count`, `overdue_action_count`, `highest_urgency_level`, `assigned_caregiver_name` per patient
- [x] 11.3 Update `GET /patients/{id}` to include `life_graph`, `pending_actions`, and `action_history` in the response
- [x] 11.4 Update `GET /actions` to support `domain`, `urgency`, `type`, `patient_id`, `is_overdue` query params and include `patient_name`, `is_overdue`, `scheduling_status` in each action row
- [x] 11.5 Add `GET /caregivers/{id}/schedule` and `GET /caregivers/{id}/assignments` to `api/routers/caregivers.py`
- [x] 11.6 Add `PUT /org` support to `api/routers/org.py` (alias or duplicate of PATCH behavior)

## 12. Mock API parity and coverage tests

- [x] 12.1 Verify Amazon reorder mock response at `POST /mock/grocery/order` returns `order_id`, `status`, `estimated_delivery` fields; update if missing
- [x] 12.2 Verify `GET /mock/caregivers/available` sort order: assigned caregiver first, then by start time, 3 business days fallback
- [x] 12.3 Add `tests/test_mock_api_coverage.py` with pytest tests asserting stable response envelope shapes for all mock endpoints used by detection and approval flows

## 13. Executor intent handler surface

- [x] 13.1 Add onboarding intent detection in `agents/executor/agent.py`: when query has no resolved patient ID and no action context, return guided onboarding message
- [x] 13.2 Implement scheduling-query routing path: resolve patient + action ID, send `SchedulingQuery` to scheduling agent, await and relay `SchedulingOptions` conversationally
- [x] 13.3 Implement action-bound question routing: extract `action_id` from context prefix, route `QuestionRequest` to the action's domain supervisor, relay `QuestionAnswer` conversationally
- [x] 13.4 Implement action-bound modification routing: extract `action_id` from context prefix, route `ModificationRequest` to health supervisor (only), relay `ModificationResult` conversationally
- [x] 13.5 Add general query fallback: for queries not matching any specific intent, fetch patient life graph from DB, construct context-aware prompt, return LLM answer conversationally
