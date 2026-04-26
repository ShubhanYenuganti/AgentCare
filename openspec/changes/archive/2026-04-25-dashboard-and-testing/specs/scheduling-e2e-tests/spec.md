## ADDED Requirements

### Requirement: Scheduling agent E2E selection tests
The test suite SHALL include E2E tests covering the full scheduling lifecycle: query → options generation → numeric selection → status transition.

#### Scenario: Full scheduling selection flow
- **WHEN** a `SchedulingQuery` is sent to the scheduling agent and the user responds with a valid numeric selection
- **THEN** the action transitions through `pending_approval` → `unconfirmed` and `assigned_caregiver` is set

#### Scenario: Cancel flow
- **WHEN** a user sends "cancel" during an active scheduling options session
- **THEN** the action transitions to `scheduling_status="cancelled"` and no caregiver is assigned

### Requirement: Scheduling API endpoint E2E tests
The test suite SHALL include tests for `POST /scheduling/{id}/assign`, `POST /scheduling/{id}/confirm`, and `POST /scheduling/{id}/decline` asserting correct status transitions and DB side effects.

#### Scenario: Assign then confirm
- **WHEN** assign is called then confirm is called on a scheduling action
- **THEN** the action ends with `scheduling_status="confirmed"` and `completed=1`

#### Scenario: Decline resets to pending
- **WHEN** decline is called on a `scheduling_status="unconfirmed"` action
- **THEN** the action resets to `scheduling_status="pending_approval"` and `assigned_caregiver` is null
