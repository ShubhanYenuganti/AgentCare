## ADDED Requirements

### Requirement: POST /patients/{id}/update returns staged classifier output
The endpoint SHALL accept `{ "content": str, "caregiver_id": str | null }`. It SHALL call the LLM with the patient's current life graph as context and the update content to produce a classification: `domain`, `operation` (`add`|`update`|`remove`), `fields_changed` (list[str]), `summary` (str), `proposed_changes` (dict). It SHALL persist the result as a `patient_updates` row with `confirmed=0, applied=0` and `proposed_changes` stored as JSON. It SHALL return `{ "requires_confirmation": true, "update_id": int, "classification": {...} }`.

#### Scenario: update produces staged record
- **WHEN** `POST /patients/pt_001/update` receives `{ "content": "Margaret's Lisinopril dose increased to 20mg" }`
- **THEN** a patient_updates row is created with `domain="health"`, `operation="update"`, `fields_changed=["medications"]`, `confirmed=0`, `applied=0`, and the response contains `requires_confirmation=true`

#### Scenario: unknown patient returns 404
- **WHEN** `POST /patients/pt_999/update` is called for a non-existent patient
- **THEN** the endpoint returns HTTP 404

### Requirement: POST /patients/{id}/update/{update_id}/confirm applies staged changes and triggers detection
The endpoint SHALL fetch the pending update record. If not found or already applied, it SHALL return 404 or 409. It SHALL call `db.apply_patient_update(update_id, proposed_changes)` and then POST `/internal/detect` with `trigger="patient_update"` and `updated_domain` set to the update's domain. It SHALL respond with `{ "applied": true, "patient_id", "update_id", "detect_status" }`.

#### Scenario: confirm applies changes and fires detection
- **WHEN** `POST /patients/pt_001/update/1/confirm` is called for an unconfirmed update
- **THEN** `apply_patient_update` is called, the update row has `applied=1`, and `/internal/detect` receives `trigger="patient_update"` with the patient_id

#### Scenario: double-confirm returns 409
- **WHEN** `POST /patients/pt_001/update/1/confirm` is called a second time on an already-applied update
- **THEN** the endpoint returns HTTP 409 Conflict

### Requirement: POST /patients/{id}/update/file applies staged update from PDF or image
The endpoint SHALL accept a multipart upload with `file` and optional `caregiver_id`. It SHALL extract text from PDF (pdfplumber) or image (call_claude_vision), then follow the same LLM classification → staged update flow as `POST /patients/{id}/update`.

#### Scenario: PDF update produces staged record
- **WHEN** `POST /patients/pt_001/update/file` receives a PDF scan of a lab report
- **THEN** text is extracted, LLM classifies the update, a staged record is created with `confirmed=0`

### Requirement: GET /patients/{id}/update-history returns all update records
The endpoint SHALL return all `patient_updates` rows for the patient ordered by `created_at DESC`. Each row SHALL include `id`, `domain`, `operation`, `fields_changed`, `summary`, `confirmed`, `applied`, `created_at`.

#### Scenario: update history lists records
- **WHEN** `GET /patients/pt_001/update-history` is called after two updates have been staged
- **THEN** both update records are returned in descending creation order

#### Scenario: unknown patient returns empty list
- **WHEN** `GET /patients/pt_999/update-history` is called for a non-existent patient
- **THEN** the endpoint returns `{ "success": true, "data": [] }` (not 404)
