## ADDED Requirements

### Requirement: Scheduling strip
The Caregiver Management view SHALL include a scheduling strip listing all actions with `scheduling_status` in `["pending_approval", "unconfirmed"]` with assignment controls.

#### Scenario: Pending scheduling actions displayed
- **WHEN** the Caregiver Management view loads
- **THEN** actions with pending scheduling status are listed with caregiver assignment dropdowns

### Requirement: Caregiver detail and schedule grid
Selecting a caregiver SHALL show a detail panel with a 14-day schedule grid populated from `GET /caregivers/{id}/schedule` and an assignment list from `GET /caregivers/{id}/assignments`.

#### Scenario: Schedule grid rendered
- **WHEN** a caregiver is selected
- **THEN** the panel renders 14 days of schedule slots with booked/available indicators

### Requirement: Confirm and decline scheduling flows
The Caregiver Management view SHALL allow confirming or declining assigned scheduling actions via `POST /scheduling/{id}/confirm` and `POST /scheduling/{id}/decline`.

#### Scenario: Confirm scheduling
- **WHEN** a user clicks "Confirm" on an unconfirmed scheduling action
- **THEN** `POST /scheduling/{id}/confirm` is called and the action card updates to `scheduling_status="confirmed"`

#### Scenario: Decline scheduling
- **WHEN** a user clicks "Decline" on an unconfirmed scheduling action
- **THEN** `POST /scheduling/{id}/decline` is called, the action resets to `pending_approval`, and an escalation notification is written

### Requirement: Deep-link preselect from Action Feed
Navigating to the Caregiver Management view from an Action Feed scheduling card SHALL preselect the relevant action in the scheduling strip.

#### Scenario: Deep-link navigation
- **WHEN** a user clicks a scheduling deep-link on an ActionCard
- **THEN** the Caregiver Management view opens with that action's row highlighted in the scheduling strip
