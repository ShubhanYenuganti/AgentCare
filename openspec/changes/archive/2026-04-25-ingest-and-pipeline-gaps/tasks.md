## 1. Schema + DB (`data/schema.sql`, `agents/shared/db.py`)

- [x] 1.1 Add `proposed_changes TEXT` column to `patient_updates` table in `data/schema.sql`
- [x] 1.2 Add migration guard in `db.get_connection()` — `ALTER TABLE patient_updates ADD COLUMN proposed_changes TEXT` wrapped in try/except (idempotent)
- [x] 1.3 Update `write_patient_update` to persist `proposed_changes` field (JSON-encode dict)
- [x] 1.4 Update `get_patient_update` to deserialize `proposed_changes` from JSON back to dict

## 2. Dependencies (`requirements.txt`, `api/main.py`)

- [x] 2.1 Add `pdfplumber` and `python-multipart` to `requirements.txt`
- [x] 2.2 Add `CORSMiddleware` to `api/main.py` — origins from `CORS_ORIGINS` env var (default `["*"]`)

## 3. Ingest Router (`api/routers/ingest.py`)

- [x] 3.1 Write `_extract_patient_from_text(text: str, patient_id_override: str | None) -> dict` — calls `call_claude_json` with extraction system prompt; validates that returned dict has `name` or `patient_id`; raises `ValueError` with raw output if not
- [x] 3.2 Write `_trigger_detect(patient_id: str, trigger: str, updated_domain: str | None = None) -> str` — POSTs to `EXECUTOR_INTERNAL_URL/internal/detect`; returns `"triggered"` or `"skipped"` (if URL not set or call fails)
- [x] 3.3 Rewrite `POST /ingest/text` — body: `{ content: str, patient_id: str | null, context: str | null }`; prepend `context` to `content` (separated by `\n\n`) before calling `_extract_patient_from_text`; then `db.write_patient()`, then `_trigger_detect("patient_create")`; return `{ patient_id, extracted, detect_status }`; return 422 on `ValueError`
- [x] 3.4 Add `POST /ingest/file` (multipart UploadFile + optional `context: str` form field + optional `patient_id: str` form field) — prepend `context` text to the file-extracted content before calling `_extract_patient_from_text`; PDF path uses pdfplumber (501 if not installed); image path uses `call_claude_vision`; return 415 for unsupported types; combined input: `"{context}\n\n{file_text}"` when context is provided

## 4. Patients Router (`api/routers/patients.py`)

- [x] 4.1 Write `_classify_update(patient_id: str, content: str) -> dict` — builds system prompt with current `serialize_complete_life_graph(patient_id)` as context; calls `call_claude_json` to produce `{ domain, operation, fields_changed, summary, proposed_changes }` 
- [x] 4.2 Add `POST /patients/{patient_id}/update` — fetch patient (404 if missing), call `_classify_update`, call `db.write_patient_update({..., proposed_changes, confirmed=0, applied=0})`; return `{ requires_confirmation: true, update_id, classification }`
- [x] 4.3 Add `POST /patients/{patient_id}/update/{update_id}/confirm` — fetch update (404 if missing, 409 if already applied); call `db.apply_patient_update(update_id, update["proposed_changes"])`; call `_trigger_detect(patient_id, "patient_update", domain)`; return `{ applied: true, patient_id, update_id, detect_status }`
- [x] 4.4 Add `POST /patients/{patient_id}/update/file` (multipart UploadFile) — extract text from PDF/image (same helpers as ingest file); call `_classify_update`; persist staged record; return same shape as task 4.2
- [x] 4.5 Add `GET /patients/{patient_id}/update-history` — call `db.get_patient_update_history(patient_id)`; return list (empty list if none, not 404)
- [x] 4.6 Remove stale blob fields (`pharmacy_name`, `pharmacy_email`, `doctor_name`, `doctor_email`) from `PatientBody` in patients router

## 5. Actions Router (`api/routers/actions.py`)

- [x] 5.1 Add `POST /actions/{action_id}/dismiss` — fetch action (404 if missing); call `db.update_action(action_id, { completed: 1, reviewed: 1, completion_date: utcnow, outcome: "dismissed" })`; return updated action
- [x] 5.2 Add `POST /actions/{action_id}/chat` — fetch action (404 if missing); call `db.write_chat_message(action_id, "user", message)`; POST to `EXECUTOR_INTERNAL_URL/message` with action context prepended to message; return `{ status: "queued", chat_id }`; 502 if executor unreachable; 503 if `EXECUTOR_INTERNAL_URL` not configured
- [x] 5.3 Add `GET /actions/{action_id}/chat-history` — fetch action (404 if missing); call `db.get_chat_history(action_id)`; return list
- [x] 5.4 Update `POST /actions/{action_id}/approve` success path — add `completion_date=datetime.utcnow().isoformat()` and `outcome="approved"` to the `update_action` call when `execution["success"]` is True

## 6. Curl + ASI:One Test Cases (documentation only — no code changes)

- [x] 6.1 Write `openspec/changes/ingest-and-pipeline-gaps/test-cases.md` with verbose curl examples for every new endpoint and ASI:One chat commands for natural-language ingest and file ingest

## 7. TASKS.md Sync

- [x] 7.1 Mark completed items in `/Users/shubhan/Autocare/TASKS.md`: check off all Section 3 items and the two remaining Section 2 items once tasks above are implemented
