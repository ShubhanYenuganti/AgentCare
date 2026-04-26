# API Dashboard Live Data

## Purpose

Defines the behavior of the API layer for serving live, SQLite-backed data to the dashboard, including response envelopes, route data binding, and consumption of enriched patient and action fields.

## Requirements

### Requirement: Live API Route Wiring
The API layer SHALL replace Sprint 1 placeholder responses with SQLite-backed live data operations for actions, patients, caregivers, scheduling, notifications, ingest, and org context.

#### Scenario: Actions endpoint returns persisted records
- **WHEN** a client requests action feed data
- **THEN** the API MUST return persisted action records with current lifecycle state and domain metadata from the shared data layer

#### Scenario: Modification endpoint updates persisted state
- **WHEN** a client submits a valid action modification payload
- **THEN** the API MUST invoke the appropriate runtime flow and return updated persisted action state

### Requirement: Consistent API Envelope and Error Contract
All Sprint 2 API endpoints SHALL return a consistent response envelope containing success indicator, data payload, and structured error metadata.

#### Scenario: Successful request uses standard envelope
- **WHEN** an endpoint completes successfully
- **THEN** the response MUST include `success=true` and a typed `data` payload matching endpoint contract

#### Scenario: Failed request uses standard error envelope
- **WHEN** an endpoint fails validation or downstream processing
- **THEN** the response MUST include `success=false` and structured error fields without leaking sensitive internal details

### Requirement: Dashboard Route Data Binding
Dashboard routes SHALL consume live API contracts and render loading, success, and error states for operator-critical pages.

#### Scenario: Actions route renders live API data
- **WHEN** dashboard loads the Actions route
- **THEN** it MUST fetch live action data, render actionable rows/cards, and expose error/empty-state UI when needed

#### Scenario: Patients and caregivers routes stay contract-parity
- **WHEN** dashboard loads Patients or Caregivers routes
- **THEN** each route MUST render data using the same canonical API contracts used by backend integration tests

### Requirement: Dashboard polling on enriched API responses
The dashboard API client SHALL consume the enriched patient and action list responses added by the backend-domain-and-api-completion change, including `pending_action_count`, `overdue_action_count`, `highest_urgency_level`, `patient_name`, `is_overdue`, and `scheduling_status` fields.

#### Scenario: Enriched patient fields displayed
- **WHEN** the Patient Roster sidebar renders a patient row
- **THEN** it displays `pending_action_count` and `highest_urgency_level` from the enriched API response

#### Scenario: is_overdue field drives banner
- **WHEN** the Action Feed renders a card with `is_overdue=true`
- **THEN** the overdue banner is displayed using the `is_overdue` field from the API response (not a client-side date calculation)
