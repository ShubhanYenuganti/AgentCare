# Backend Integration Tests

## Purpose

Defines the integration test suite for the backend, covering the patient update pipeline, file ingest, and executor internal detect endpoint with fan-out behavior.

## Requirements

### Requirement: Patient update pipeline integration tests
The test suite SHALL include integration tests for the full patient update submit → confirm flow that assert detection is triggered after confirmation.

#### Scenario: Submit and confirm triggers detection
- **WHEN** `POST /patients/{id}/update` is called and then `POST /patients/{id}/update/{uid}/confirm` is called
- **THEN** the internal detect endpoint is called with `trigger="patient_update"` and new actions are written to the DB

### Requirement: File ingest integration tests
The test suite SHALL include integration tests for `POST /ingest/file` asserting patient extraction, DB write, and detection trigger.

#### Scenario: PDF file ingest end-to-end
- **WHEN** a PDF file is posted to `POST /ingest/file`
- **THEN** a patient record is written to the DB and a `patient_create` detection trigger fires

### Requirement: Executor internal detect endpoint tests
The test suite SHALL include tests for `POST /internal/detect` for both `patient_create` and `patient_update` triggers asserting fan-out message structure.

#### Scenario: patient_create fan-out
- **WHEN** `POST /internal/detect` is called with `trigger="patient_create"`
- **THEN** the executor fans out to all four domain supervisors

#### Scenario: patient_update fan-out with domain hint
- **WHEN** `POST /internal/detect` is called with `trigger="patient_update"` and `updated_domain="health"`
- **THEN** the executor fans out only to the health supervisor
