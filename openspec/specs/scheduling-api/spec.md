# Scheduling API

## Purpose

Defines the REST API endpoints for scheduling action lifecycle management: assign, confirm, and decline flows with appropriate state validation.

## Requirements

### Requirement: Assign scheduling action
`POST /scheduling/{id}/assign` SHALL accept a caregiver ID, validate the action exists and has `scheduling_status="pending_approval"`, assign the caregiver, set `scheduling_status="unconfirmed"`, and return the updated action.

#### Scenario: Successful assign
- **WHEN** a valid `action_id` with `scheduling_status="pending_approval"` receives an assign request with a valid caregiver ID
- **THEN** the endpoint sets `assigned_caregiver`, sets `scheduling_status="unconfirmed"`, and returns `200 ok(action)`

#### Scenario: Action not in pending state
- **WHEN** the action's `scheduling_status` is not `"pending_approval"`
- **THEN** the endpoint returns `409` with an error message

### Requirement: Confirm scheduling action
`POST /scheduling/{id}/confirm` SHALL validate the action has `scheduling_status="unconfirmed"`, set `scheduling_status="confirmed"` and `completed=1`, write a confirmation notification, and return the updated action.

#### Scenario: Successful confirm
- **WHEN** an action with `scheduling_status="unconfirmed"` receives a confirm request
- **THEN** the endpoint sets `scheduling_status="confirmed"`, `completed=1`, `completion_date`, and returns `200 ok(action)`

### Requirement: Decline scheduling action
`POST /scheduling/{id}/decline` SHALL free the booked slot, reset `scheduling_status="pending_approval"`, clear `assigned_caregiver`, write an escalation notification, and return the updated action.

#### Scenario: Successful decline
- **WHEN** an action with `scheduling_status="unconfirmed"` receives a decline request
- **THEN** the endpoint clears `assigned_caregiver`, resets `scheduling_status="pending_approval"`, writes an escalation notification, and returns `200 ok(action)`
