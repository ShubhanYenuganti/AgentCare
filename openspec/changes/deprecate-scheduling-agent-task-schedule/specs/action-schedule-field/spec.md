## ADDED Requirements

### Requirement: Schedule field on actions
Actions SHALL support an optional `schedule` field stored as a JSON TEXT column in `action_history`. When present, the field SHALL contain `start_time` (UTC ISO-8601 string), `end_time` (UTC ISO-8601 string), and an optional `recurrence` object with `day` (lowercase weekday name) and `freq` ("weekly" | "daily").

#### Scenario: Action with schedule field stored and retrieved
- **WHEN** a domain agent or executor sets `schedule` on an action
- **THEN** the `schedule` JSON is persisted in `action_history.schedule` and returned verbatim by `GET /actions` and `GET /actions/{action_id}`

#### Scenario: Action without schedule field
- **WHEN** a domain agent does not set `schedule` on an action
- **THEN** `schedule` is `null` in the API response and no availability logic is triggered

### Requirement: DB migration for schedule column
The `action_history` table SHALL have a nullable TEXT column `schedule` added via `ALTER TABLE action_history ADD COLUMN schedule TEXT`.

#### Scenario: Existing rows unaffected
- **WHEN** the migration runs on a database with existing action rows
- **THEN** existing rows have `schedule = NULL` and all existing functionality continues unchanged

### Requirement: scheduling_status field deprecated
The `scheduling_status` field SHALL no longer be written by any agent or the executor. The DB column remains (no destructive migration) but API responses SHALL omit it or return its existing stored value for legacy rows only.

#### Scenario: New actions do not set scheduling_status
- **WHEN** the executor or any domain agent creates or updates an action after this change
- **THEN** `scheduling_status` is not written; the field is null on new rows

### Requirement: caregiver_assessment manual action type removed
The `manual_action_type = "caregiver_assessment"` value SHALL no longer be emitted by any agent. Existing rows with this value are unaffected.

#### Scenario: No new caregiver_assessment actions created
- **WHEN** the executor processes a time-oriented task
- **THEN** the resulting action does not have `manual_action_type = "caregiver_assessment"`
