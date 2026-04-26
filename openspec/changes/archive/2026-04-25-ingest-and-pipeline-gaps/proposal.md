## Why

The ingest router currently proxies raw text to the executor without extracting patient data, the patient update pipeline has no staged-confirmation flow, and several FastAPI endpoints required by the spec (action chat, dismiss, update history, file ingest, CORS) are absent. These gaps mean the system cannot onboard new patients from natural language or files, cannot stage and confirm data changes, and cannot support the dashboard's action-chat or update-history UX.

## What Changes

- Replace `/ingest/text` proxy with spec extraction flow: LLM extracts structured patient record → `write_patient()` → POST `/internal/detect` with `patient_create` trigger
- Add `POST /ingest/file` supporting PDF (pdfplumber) and image (call_claude_vision) with same extraction+detect flow
- Add `POST /patients/{id}/update` — LLM classifier returns `domain`, `operation`, `fields_changed`, `summary`, `proposed_changes`; persists update record; responds with `requires_confirmation=true`
- Add `proposed_changes` column to `patient_updates` schema table
- Add `POST /patients/{id}/update/{update_id}/confirm` — applies staged changes via `apply_patient_update`, triggers `internal/detect` with `patient_update`
- Add `POST /patients/{id}/update/file` — PDF/image extraction into same staged-confirm flow
- Add `GET /patients/{id}/update-history` — returns `patient_updates` rows for the patient
- Add `POST /actions/{id}/chat` — routes chat message through executor intent pipeline bound to the action context
- Add `GET /actions/{id}/chat-history` — returns `action_chat` rows
- Add `POST /actions/{id}/dismiss` — soft-completes an action without API execution
- Add CORS middleware to FastAPI app for dashboard origin
- Update approve path to write `completion_date` and `outcome` to `action_history`

## Capabilities

### New Capabilities

- `ingest-text-extraction`: LLM extraction flow for `/ingest/text` — parse free-form text into structured patient record, persist, trigger detection
- `ingest-file`: `POST /ingest/file` endpoint accepting multipart PDF or image, extract patient data, persist, trigger detection
- `patient-update-pipeline`: Staged update flow — `POST /patients/{id}/update`, confirm, file-variant, and update-history read
- `action-chat-api`: `POST /actions/{id}/chat` and `GET /actions/{id}/chat-history` endpoints wiring API requests into executor chat pipeline
- `action-lifecycle-api`: `POST /actions/{id}/dismiss` and approve-path `completion_date`/`outcome` writes

### Modified Capabilities

- `foundation-runtime-bootstrap`: CORS middleware required on FastAPI app; `patient_updates` table gains `proposed_changes TEXT` column

## Impact

- `api/main.py` — CORS middleware added
- `api/routers/ingest.py` — `/text` rewritten, `/file` added
- `api/routers/patients.py` — `/update`, `/update/{id}/confirm`, `/update/file`, `/update-history` added; stale blob fields removed from `PatientBody`
- `api/routers/actions.py` — `/chat`, `/chat-history`, `/dismiss` added; approve writes completion fields
- `data/schema.sql` — `patient_updates.proposed_changes TEXT` column added
- `agents/shared/db.py` — `write_patient_update` and `get_patient_update` gain `proposed_changes` field
- Dependencies: `pdfplumber` (PDF extraction), `python-multipart` (FastAPI file upload)
