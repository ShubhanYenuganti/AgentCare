## ADDED Requirements

### Requirement: Caregiver assignment panel activated by action
The Caregivers view SHALL accept an `action_id` query parameter. When present, the view SHALL display an assignment panel for that action above the caregiver list, showing the action description and a list of assignable caregivers.

#### Scenario: Assignment panel opens from URL
- **WHEN** the user navigates to `/caregivers?action_id=<id>`
- **THEN** the Caregivers view fetches the action by ID, displays its description in a panel header, and renders the caregiver assignment list below

#### Scenario: No action_id — normal view
- **WHEN** the user navigates to `/caregivers` without an `action_id` query param
- **THEN** the normal caregiver roster is shown with no assignment panel

### Requirement: Availability-filtered caregiver list
When the selected action has a non-null `schedule` field, the caregiver list in the assignment panel SHALL only show caregivers who have at least one `caregiver_schedule` slot overlapping the action's `[start_time, end_time]` window with `available=1` and `booked=0`.

#### Scenario: Caregivers filtered by schedule overlap
- **WHEN** the action has `schedule.start_time` and `schedule.end_time` set
- **THEN** only caregivers with an overlapping available unbooked slot are shown in the assignment panel

#### Scenario: No caregivers available in window
- **WHEN** the schedule window has no available caregivers
- **THEN** the panel shows a message "No caregivers available for this time window" and falls back to showing all caregivers without filtering

### Requirement: Workload-ranked caregiver list
When the selected action has no `schedule` field, the caregiver list SHALL be ranked ascending by total load: `(count of assigned actions) + (count of booked schedule slots)`.

#### Scenario: Caregivers ranked by workload
- **WHEN** the action has no `schedule` field
- **THEN** the assignment panel shows all caregivers ordered by ascending load, with the least-loaded caregiver first

### Requirement: Assign caregiver to action
Each caregiver row in the assignment panel SHALL have an **Assign** button. Clicking it SHALL call `PATCH /actions/{action_id}` with `assigned_caregiver` set to the caregiver's ID. If the action has a `schedule` field and a matching slot exists, that slot's `booked` flag SHALL be set to 1.

#### Scenario: Successful assignment without schedule
- **WHEN** user clicks Assign on a caregiver for an action with no `schedule`
- **THEN** `PATCH /actions/{action_id}` is called with the caregiver ID, the action list refreshes, and the panel closes

#### Scenario: Successful assignment with schedule
- **WHEN** user clicks Assign on a caregiver for an action with a `schedule`
- **THEN** `PATCH /actions/{action_id}` is called with the caregiver ID, the matching `caregiver_schedule` slot is marked `booked=1`, the action list refreshes, and the panel closes

### Requirement: Backend endpoint for availability query
The API SHALL expose `GET /caregivers/available?start_time=<iso>&end_time=<iso>` returning caregivers with overlapping available unbooked slots. When no query params are provided it SHALL return all caregivers ranked by ascending load.

#### Scenario: Availability query with time window
- **WHEN** `GET /caregivers/available?start_time=X&end_time=Y` is called
- **THEN** the response contains only caregivers with `available=1, booked=0` slots overlapping `[X, Y]`

#### Scenario: Workload query without time window
- **WHEN** `GET /caregivers/available` is called without params
- **THEN** the response contains all caregivers ordered by ascending `(assigned_action_count + booked_slot_count)`
