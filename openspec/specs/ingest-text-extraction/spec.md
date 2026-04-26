## ADDED Requirements

### Requirement: POST /ingest/text performs LLM extraction and patient persistence
The endpoint SHALL accept `{ "content": str, "patient_id": str | null }`. It SHALL call the Claude LLM with a structured extraction prompt to parse the text into the spec Section 3.3 patient shape. It SHALL call `db.write_patient()` with the extracted data and then POST `{ "patient_id", "trigger": "patient_create" }` to the executor `POST /internal/detect`. It SHALL return `{ "success": true, "data": { "patient_id", "extracted", "detect_status" } }`. If LLM output cannot be parsed into a dict containing at least `name` or `patient_id`, it SHALL return HTTP 422.

#### Scenario: valid onboarding text creates patient and triggers detection
- **WHEN** `POST /ingest/text` receives `{ "content": "New patient Margaret Chen, age 72, lives at 12 Oak Ave..." }`
- **THEN** a patient row is written to the DB with `name="Margaret Chen"` and the executor `/internal/detect` receives `trigger="patient_create"` for the new patient_id

#### Scenario: unparseable text returns 422
- **WHEN** `POST /ingest/text` receives `{ "content": "hello world" }` and the LLM cannot extract a name or patient_id
- **THEN** the endpoint returns HTTP 422 with `{ "success": false, "error": "extraction_failed", "raw": "<llm_output>" }`

#### Scenario: executor not configured falls back gracefully
- **WHEN** `EXECUTOR_INTERNAL_URL` is not set and `POST /ingest/text` receives valid patient text
- **THEN** the patient is written to DB and the response contains `"detect_status": "skipped"` (no crash)

#### Scenario: existing patient_id is preserved in extraction
- **WHEN** `POST /ingest/text` receives `{ "content": "...", "patient_id": "pt_001" }` with a patient_id override
- **THEN** `write_patient` is called with `patient_id="pt_001"` regardless of what the LLM extracted
