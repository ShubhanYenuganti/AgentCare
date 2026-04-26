## Why

The scheduling agent added complexity without clear value: it introduced a separate `scheduling_status` field and a `caregiver_assessment` manual action type that duplicated intent already expressed by the action itself. Time-oriented tasks need a first-class `schedule` field on the action so the frontend can handle assignment with full availability awareness, without a dedicated agent or side-channel status.

## What Changes

- **BREAKING**: Remove `scheduling_status` field from action model and all agent outputs
- **BREAKING**: Remove `manual_action_type = "caregiver_assessment"` — the scheduling agent no longer produces this type
- Deprecate the scheduling agent (`agents/scheduling/agent.py`) — no longer invoked by the executor
- Add `schedule` field to the action model: JSON payload with `start_time` (UTC ISO-8601), `end_time` (UTC ISO-8601), and optional `recurrence` (e.g. `{"day": "thursday", "freq": "weekly"}`)
- Executor/domain agents set `schedule` on time-oriented tasks instead of routing to scheduling agent
- ActionCard gains a 5th button: **Schedule Task** (rightmost), visible when action is not yet assigned
- Clicking Schedule Task navigates to the Caregiver page pre-filtered to that action, showing assignable caregivers
- If `schedule` is present: caregivers are pre-filtered to those available during the scheduled window (cross-referenced against `caregiver_schedule` table)
- If `schedule` is absent: caregivers are ranked by ascending total assigned/scheduled workload
- Assign button on each caregiver row links the caregiver to that action

## Capabilities

### New Capabilities
- `action-schedule-field`: `schedule` JSON field on actions — model, DB migration, executor output, agent output
- `caregiver-task-assignment`: Caregiver assignment flow launched from ActionCard, with availability filtering and workload ranking

### Modified Capabilities
- `dashboard-action-feed`: ActionCard gains Schedule Task button; `scheduling_status` display removed
- `executor-intent-detection-orchestration`: Executor no longer routes to scheduling agent; emits `schedule` field on time-oriented actions
- `scheduling-agent-workflow`: Deprecated — agent is no longer invoked; spec updated to reflect removal

## Impact

- `agents/shared/models.py` — add `schedule` field, remove `scheduling_status` and `caregiver_assessment` references
- `agents/scheduling/agent.py` — deprecated (not deleted, but not registered or invoked)
- `agents/executor/agent.py` — remove scheduling agent routing branch
- `api/routers/actions.py` — schema changes propagate through existing endpoints
- `dashboard/src/components/ActionCard.tsx` — add Schedule Task button
- `dashboard/src/views/Caregivers.tsx` — add assignment panel with availability/workload logic
- `dashboard/src/api/client.ts` — new assign-caregiver-to-action mutation
- DB: `action_history` table needs `schedule` column (TEXT, nullable)
