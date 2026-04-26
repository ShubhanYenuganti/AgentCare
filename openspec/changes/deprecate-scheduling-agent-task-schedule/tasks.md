## 1. DB & Schema

- [x] 1.1 Add `schedule TEXT` column to `action_history` in `data/schema.sql`
- [x] 1.2 Add `ALTER TABLE action_history ADD COLUMN IF NOT EXISTS schedule TEXT` migration path in `agents/shared/db.py` `init_db` (or run directly against existing DB)

## 2. Backend Model & Agent Cleanup

- [x] 2.1 Add `schedule: dict | None` field to the `Action` / action output model in `agents/shared/models.py`
- [x] 2.2 Remove `scheduling_status` writes from `agents/scheduling/agent.py` (mark file as deprecated with a top-level comment; do not delete)
- [x] 2.3 Remove the `scheduling` intent routing branch from `agents/executor/agent.py` (the `_SCHEDULING_KEYWORDS` dispatch path and any `caregiver_assessment` manual action type assignment)
- [x] 2.4 Remove `caregiver_assessment` from any `manual_action_type` assignments across all domain agents and the executor
- [x] 2.5 Update `agents/shared/db.py` `update_action` / `write_action` helpers to accept and persist the `schedule` field

## 3. API Layer

- [x] 3.1 Add `schedule` to the action serialization in `api/routers/actions.py` so it is included in `GET /actions` and `GET /actions/{action_id}` responses
- [x] 3.2 Add `GET /caregivers/available` endpoint to `api/routers/caregivers.py` — accepts optional `start_time` and `end_time` query params; returns availability-filtered list (with schedule) or workload-ranked list (without)
- [x] 3.3 Implement DB helper in `agents/shared/db.py`: `get_caregivers_available(start_time, end_time)` and `get_caregivers_by_workload()` — used by the new endpoint
- [x] 3.4 Update `PATCH /actions/{action_id}` handler to book the matching `caregiver_schedule` slot (`booked=1`) when `assigned_caregiver` is set and the action has a `schedule`

## 4. Frontend — Types & API Client

- [x] 4.1 Add `schedule?: { start_time: string; end_time: string; recurrence?: { day: string; freq: string } } | null` to the `Action` interface in `dashboard/src/types/index.ts`
- [x] 4.2 Remove `scheduling_status` from the `Action` interface
- [x] 4.3 Add `useGetCaregiversAvailableQuery` to `dashboard/src/api/client.ts` — calls `GET /caregivers/available` with optional `start_time`/`end_time` params
- [x] 4.4 Add `useAssignCaregiverToActionMutation` to `dashboard/src/api/client.ts` — calls `PATCH /actions/{action_id}` with `{ assigned_caregiver }` and invalidates `["Action", "Caregiver"]`

## 5. Frontend — ActionCard

- [x] 5.1 Add **Schedule Task** button as the rightmost button in `ActionCard`, visible when `action.completed === 0` and `action.assigned_caregiver` is null
- [x] 5.2 On click, navigate to `/caregivers?action_id=<action_id>` using React Router `useNavigate`
- [x] 5.3 Remove any rendering of `scheduling_status` from ActionCard

## 6. Frontend — Caregivers Assignment Panel

- [x] 6.1 Read `action_id` from URL query params in `dashboard/src/views/CaregiverManagement.tsx` on mount
- [x] 6.2 When `action_id` is present, fetch the action and render an assignment panel above the caregiver list showing the action description
- [x] 6.3 If action has `schedule`: call `useGetCaregiversAvailableQuery` with `start_time`/`end_time`; render filtered caregiver list; show fallback message and all caregivers if result is empty
- [x] 6.4 If action has no `schedule`: call `useGetCaregiversAvailableQuery` without params; render workload-ranked caregiver list
- [x] 6.5 Each caregiver row has an **Assign** button; on click call `useAssignCaregiverToActionMutation`, then navigate back to `/` (action feed) on success
- [x] 6.6 Add a close/cancel button on the assignment panel that navigates back without assigning

## 7. Verification

- [ ] 7.1 Confirm `GET /actions` no longer returns `scheduling_status` on new rows
- [ ] 7.2 Confirm `GET /caregivers/available?start_time=X&end_time=Y` returns only overlapping available caregivers
- [ ] 7.3 Confirm ActionCard shows Schedule Task button on unassigned actions and hides it after assignment
- [ ] 7.4 Confirm assignment panel opens at `/caregivers?action_id=<id>` and assignment succeeds end-to-end
