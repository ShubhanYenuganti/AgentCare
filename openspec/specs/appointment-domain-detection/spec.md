# Appointment Domain Detection

## Purpose

Defines the behavior of the appointment domain worker for detecting overdue appointments, generating transport planning drafts, and producing visit prep drafts for upcoming appointments.

## Requirements

### Requirement: Overdue appointment detection
The appointment worker SHALL detect appointments whose scheduled date has passed without a `completed=1` record and generate a `type="overdue_appointment"` draft.

#### Scenario: Appointment overdue
- **WHEN** an appointment's `scheduled_date` is in the past and `completed=0`
- **THEN** the worker generates an `ActionDraft` with `type="overdue_appointment"` and `urgency_level="high"`

#### Scenario: Appointment completed
- **WHEN** an appointment is marked `completed=1`
- **THEN** no overdue draft is generated for that appointment

### Requirement: Transport planning with Google Maps
The appointment worker SHALL call the Google Maps Distance Matrix API to compute estimated travel time for upcoming appointments that require transport and generate a `type="transport_planning"` scheduling-task draft including distance and ETA in `draft_content`.

#### Scenario: Transport required and Maps key available
- **WHEN** an upcoming appointment has `transport_required=1` and `GOOGLE_MAPS_API_KEY` is set
- **THEN** the worker calls Distance Matrix, embeds ETA in `draft_content`, sets `manual_action_type="transport"`, and outputs a scheduling-task `ActionDraft`

#### Scenario: Maps key absent
- **WHEN** `GOOGLE_MAPS_API_KEY` is not set
- **THEN** the worker generates a transport draft without ETA data and logs a warning

### Requirement: Visit prep draft
The appointment worker SHALL generate a `type="visit_prep"` draft for appointments scheduled within 48 hours that do not already have a visit prep action.

#### Scenario: Appointment within 48 hours
- **WHEN** an appointment is scheduled within 48 hours and no existing `visit_prep` action for that appointment exists
- **THEN** the worker generates an `ActionDraft` with `type="visit_prep"` and `urgency_level="medium"`

### Requirement: Scheduling task output structure
The appointment worker SHALL output scheduling-task drafts with `manual_action_type` set and all scheduling metadata fields populated (`review_by`, `recipient_type`, `recipient_email`).

#### Scenario: Scheduling draft structure valid
- **WHEN** the worker generates any scheduling-task draft
- **THEN** the `ActionDraft` has non-null `manual_action_type`, `review_by`, and `recipient_type` fields
