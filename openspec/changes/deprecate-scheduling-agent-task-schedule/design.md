## Context

The current system routes time-oriented tasks through a dedicated scheduling agent (`agents/scheduling/agent.py`). That agent writes `scheduling_status` ("pending_approval", "unconfirmed", "no_availability", "cancelled") and sets `manual_action_type = "caregiver_assessment"` on actions. The frontend ActionCard renders this status but has no awareness of caregiver availability windows — assignment is manual and uninformed.

The `caregiver_schedule` table already tracks per-caregiver time slots (`date`, `start_time`, `end_time`, `available`, `booked`). The infrastructure for availability-aware assignment exists; it just isn't surfaced to the user.

## Goals / Non-Goals

**Goals:**
- Add a first-class `schedule` field to actions (DB column + model + API output)
- Domain agents and the executor emit `schedule` for time-oriented tasks instead of routing to the scheduling agent
- Remove `scheduling_status` from action writes and API responses
- ActionCard gets a **Schedule Task** button that navigates to Caregivers with the action pre-selected
- Caregiver assignment panel: availability-filtered list (when `schedule` present) or workload-ranked list (when absent)
- Assigning a caregiver sets `assigned_caregiver` on the action and marks the slot `booked` in `caregiver_schedule`

**Non-Goals:**
- Deleting the scheduling agent file (deprecated, not removed)
- Calendar UI or recurring schedule management
- Real-time slot conflict resolution across multiple concurrent assignments
- Notifying caregivers of assignment (out of scope for this change)

## Decisions

### 1. `schedule` field shape
```json
{
  "start_time": "2026-05-01T16:00:00Z",
  "end_time":   "2026-05-01T20:00:00Z",
  "recurrence": { "day": "thursday", "freq": "weekly" }
}
```
Stored as TEXT (JSON) in `action_history.schedule`. Optional — actions without a time constraint leave it null. `recurrence` is optional within the object.

**Alternative considered**: Separate `start_time`/`end_time` columns. Rejected — keeping it as a single JSON blob avoids a migration that adds two nullable columns and keeps the model flexible for future recurrence fields.

### 2. Availability matching logic
When `schedule` is present, a caregiver is considered available if they have at least one `caregiver_schedule` row overlapping the action's `[start_time, end_time]` window with `available=1` and `booked=0`. Overlap check: `slot.start < action.end AND slot.end > action.start`.

**Alternative considered**: Matching only on `day` from `recurrence`. Rejected — the `start_time`/`end_time` fields carry the concrete next occurrence, which is more actionable for the assigning user.

### 3. Workload ranking (no schedule)
When `schedule` is absent, caregivers are ranked ascending by `(COUNT of assigned actions) + (COUNT of booked schedule slots)`. This is a simple proxy for load; it doesn't account for action duration. Sufficient for the current data volume.

### 4. Assignment writes
`PATCH /actions/{action_id}` already accepts `assigned_caregiver`. The new assignment button calls this endpoint. Additionally, if `schedule` is present and a matching slot exists, the slot's `booked` flag is set to 1 in `caregiver_schedule`.

### 5. Navigation pattern: ActionCard → Caregivers
Schedule Task button uses `navigate("/caregivers?action_id=<id>")`. The Caregivers view reads the `action_id` query param on mount, fetches that action, and activates the assignment panel. No shared global state needed — URL carries the intent.

### 6. Executor change
The executor's `_SCHEDULING_KEYWORDS` branch that dispatches to the scheduling agent is removed. Domain agents (health, appointment, etc.) are responsible for setting `schedule` on relevant output actions. The executor passes the field through unchanged.

## Risks / Trade-offs

- **`scheduling_status` removal is breaking** → Any external consumer or seed data referencing `scheduling_status` will silently get `null`. Mitigated by DB column being nullable (no constraint violation); old rows are unaffected.
- **Caregiver slot coverage gap** → If no `caregiver_schedule` rows exist for a caregiver, they won't appear in the availability-filtered list even if they're free. Mitigated by falling back to showing all caregivers with a warning when the filtered list is empty.
- **Recurrence is stored but not acted on** → The `recurrence` subfield is stored for future use but the assignment UI only shows the next concrete slot. Mitigated by documenting this limitation in the spec.

## Migration Plan

1. Add `schedule TEXT` column to `action_history` (SQLite `ALTER TABLE ADD COLUMN` — safe, nullable, no rewrite)
2. No data migration needed — existing rows keep `scheduling_status` values; column stays in DB but is no longer written by agents (API can still return it for old rows)
3. Deploy backend changes first (new column, updated models, executor changes)
4. Deploy frontend changes (ActionCard button, Caregivers assignment panel)
5. Rollback: remove `schedule` column addition is a schema-only revert; no data loss since the column is additive

## Open Questions

- Should assigning a caregiver to an action also mark the action `completed = 1`, or leave it pending until the task is done? (Current assumption: leave pending — assignment ≠ completion.)
- When the `recurrence` field is present, should subsequent occurrences auto-generate new actions? Out of scope here but worth speccing later.
