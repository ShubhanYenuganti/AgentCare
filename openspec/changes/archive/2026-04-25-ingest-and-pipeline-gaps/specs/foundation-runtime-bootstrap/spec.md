## ADDED Requirements

### Requirement: FastAPI app includes CORS middleware
The FastAPI application SHALL include `CORSMiddleware` configured with origins from the `CORS_ORIGINS` environment variable (JSON array string, defaulting to `["*"]`). All methods and headers SHALL be allowed.

#### Scenario: CORS headers present on preflight
- **WHEN** an OPTIONS request is sent to any API route with `Origin: http://localhost:5173`
- **THEN** the response includes `Access-Control-Allow-Origin` header

### Requirement: patient_updates table includes proposed_changes column
The `patient_updates` table SHALL include a `proposed_changes TEXT` column storing a JSON-serialized dict of the proposed field changes produced by the LLM classifier.

#### Scenario: proposed_changes persisted and retrievable
- **WHEN** a staged update record is written with `proposed_changes={"medications": [...]}`
- **THEN** `db.get_patient_update(update_id)["proposed_changes"]` returns the dict deserialized from JSON
