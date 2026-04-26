## ADDED Requirements

### Requirement: CORS middleware
The FastAPI application SHALL include CORS middleware allowing requests from configured dashboard origins (`DASHBOARD_ORIGIN` env var, defaulting to `http://localhost:5173`).

#### Scenario: CORS preflight from dashboard origin
- **WHEN** a preflight OPTIONS request arrives from the dashboard origin
- **THEN** the server returns appropriate CORS headers and `200`

### Requirement: Enriched patient list response
`GET /patients` SHALL include per-patient urgency summary fields: `pending_action_count`, `overdue_action_count`, `highest_urgency_level`, and `assigned_caregiver_name`.

#### Scenario: Patient with pending actions
- **WHEN** a patient has active pending actions
- **THEN** `GET /patients` returns those counts and the highest urgency level in each patient object

### Requirement: Enriched patient detail response
`GET /patients/{id}` SHALL return the full life graph plus `pending_actions` (list of active action summaries) and `action_history` (completed/dismissed actions).

#### Scenario: Full detail response
- **WHEN** `GET /patients/{id}` is called for an existing patient
- **THEN** the response includes `life_graph`, `pending_actions`, and `action_history` fields

### Requirement: Action list filtering
`GET /actions` SHALL support query parameters: `domain`, `urgency`, `type`, `patient_id`, `is_overdue` (boolean). Response items SHALL include enriched fields: `patient_name`, `is_overdue`, `scheduling_status`.

#### Scenario: Filter by domain
- **WHEN** `GET /actions?domain=health` is called
- **THEN** only actions with `domain="health"` are returned

#### Scenario: Filter by overdue
- **WHEN** `GET /actions?is_overdue=true` is called
- **THEN** only actions whose `review_by` date is in the past and `completed=0` are returned

### Requirement: Caregiver schedule and assignment endpoints
`GET /caregivers/{id}/schedule` SHALL return the caregiver's 14-day schedule slots. `GET /caregivers/{id}/assignments` SHALL return their currently assigned actions.

#### Scenario: Caregiver schedule returned
- **WHEN** `GET /caregivers/{id}/schedule` is called for an existing caregiver
- **THEN** the response includes a list of schedule slots for the next 14 days

### Requirement: Org router PUT support
`PUT /org` SHALL behave identically to `PATCH /org` (full or partial update), supporting idempotent org profile updates from the dashboard.

#### Scenario: PUT org profile
- **WHEN** `PUT /org` is called with a valid org profile payload
- **THEN** the org profile is updated and the updated profile is returned
