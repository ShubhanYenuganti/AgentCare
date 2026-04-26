# Dashboard Patient Roster

## Purpose

Defines the behavior of the Patient Roster view in the dashboard, including the split layout, add patient workflow, staged update confirmation, and update history panel.

## Requirements

### Requirement: Patient Roster split layout
The Patient Roster view SHALL render a two-column layout: a patient sidebar listing all patients with urgency indicators, and a detail panel showing the selected patient's full life graph.

#### Scenario: Patient selected
- **WHEN** a user clicks a patient in the sidebar
- **THEN** the detail panel updates to show that patient's full life graph, pending actions count, and action history

### Requirement: Add patient workflow
The Patient Roster SHALL include an "Add Patient" button that opens a multi-step form for text or file-based patient ingestion.

#### Scenario: Text ingest
- **WHEN** a user submits free-form patient text via the add form
- **THEN** the form posts to `POST /ingest/text` and the roster refreshes on success

#### Scenario: File ingest
- **WHEN** a user uploads a PDF or image via the add form
- **THEN** the form posts to `POST /ingest/file` with the file as multipart and the roster refreshes on success

### Requirement: Update patient staged confirmation
The Patient Roster SHALL support patient updates via a staged confirmation state machine: submit → show proposed changes → confirm or cancel.

#### Scenario: Update submitted and confirmed
- **WHEN** a user submits an update and clicks "Confirm" on the proposed changes panel
- **THEN** the dashboard calls `POST /patients/{id}/update/{update_id}/confirm` and the patient detail panel refreshes

#### Scenario: Update cancelled
- **WHEN** a user clicks "Cancel" on the proposed changes panel
- **THEN** the staged update is discarded and the patient detail panel returns to its prior state

### Requirement: Update history panel
The patient detail panel SHALL include an "Update History" tab that fetches and renders all update records from `GET /patients/{id}/update-history`.

#### Scenario: Update history loaded
- **WHEN** the user clicks the "Update History" tab
- **THEN** the panel fetches `GET /patients/{id}/update-history` and renders each update record with timestamp, domain, and summary
