# Scheduling Agent Workflow

## Purpose

Defines the scheduling agent's message-driven workflow for generating caregiver options, handling user selections, and processing decline events.

## Requirements

### Requirement: Scheduling options generation
The scheduling agent SHALL handle `SchedulingQuery` messages by calling `GET /mock/caregivers/available` with the required time window, persist the returned options on the action record, and send a numbered options list to the requester address.

#### Scenario: Options generated successfully
- **WHEN** the scheduling agent receives a `SchedulingQuery` with a valid `action_id` and `patient_id`
- **THEN** it calls the caregiver availability mock API, persists the options in `caregiver_options_json` on the action, sets `scheduling_status="pending_approval"`, and sends a `SchedulingOptions` message with numbered slots to the requester

#### Scenario: No caregivers available
- **WHEN** the caregiver availability API returns an empty list
- **THEN** the agent sends a `SchedulingOptions` message with `options=[]` and sets `scheduling_status="no_availability"`

### Requirement: Chat-selection handler
The scheduling agent SHALL handle numeric selection messages (1–N or "cancel") against a pending `SchedulingOptions` session, assign the selected caregiver, book the slot, write a notification, and set `scheduling_status="unconfirmed"`.

#### Scenario: Valid numeric selection
- **WHEN** a user sends a numeric choice matching a pending options session
- **THEN** the agent assigns the caregiver, calls `POST /mock/caregivers/book`, sets `scheduling_status="unconfirmed"`, and writes a confirmation notification

#### Scenario: Cancel selection
- **WHEN** a user sends "cancel" during a pending options session
- **THEN** the agent clears the pending session, sets `scheduling_status="cancelled"`, and writes a cancellation notification

### Requirement: Decline flow
The scheduling agent SHALL handle decline events by freeing the booked slot, resetting `scheduling_status` to `"pending_approval"`, clearing the caregiver assignment, and writing an escalation notification.

#### Scenario: Caregiver declines
- **WHEN** a decline event is received for a confirmed scheduling action
- **THEN** the agent calls `POST /mock/caregivers/release` to free the slot, clears `assigned_caregiver`, resets `scheduling_status="pending_approval"`, and writes an `ExpirationEscalation`
