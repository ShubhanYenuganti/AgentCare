## Context

The Sprint 2 data layer is now normalized and the executor has a working `/internal/detect` endpoint. The next gap is the boundary between external input (HTTP POST of text or file) and the agent pipeline. Currently `/ingest/text` is a thin proxy that forwards raw content to the executor's `/ingest` handler, which interprets the intent via keyword matching rather than extracting a structured patient record. The patient update pipeline has a DB schema and helpers but no HTTP surface. Several action lifecycle endpoints (`chat`, `dismiss`, `chat-history`) exist in the DB layer but have no API routes.

## Goals / Non-Goals

**Goals:**
- Wire `/ingest/text` to the spec extraction flow: LLM → `write_patient()` → `POST /internal/detect`
- Add `/ingest/file` with pdfplumber for PDF, `call_claude_vision` for images
- Add staged patient update flow: propose → confirm → trigger detection
- Add action chat, dismiss, and chat-history API routes
- Add CORS middleware and approve-path completion metadata

**Non-Goals:**
- Domain worker logic (health, appointment, grocery, financial detection checks) — Sprint 2 Section 4
- Scheduling agent workflow — Sprint 2 Section 5
- Dashboard UI — Sprint 3+

## Decisions

**Decision: `/ingest/text` calls LLM directly in the FastAPI router, not via executor**
The ingest router already has access to `db.write_patient` and can POST to `EXECUTOR_INTERNAL_URL/internal/detect`. Adding an LLM extraction step in the router keeps the ingest path fully synchronous with a deterministic response. The executor's chat pipeline is designed for interactive Q&A and would add unnecessary latency and state complexity for a one-shot extraction.
- Alternative: send raw text to executor and have executor do extraction. Rejected — the executor's intent classifier would route onboarding text as "detection" with no structured record written to DB.

**Decision: LLM extraction uses a structured JSON prompt returning the spec Section 3.3 patient shape**
The extraction prompt asks Claude to return a dict matching the `write_patient` input contract (top-level patient fields + nested `medications`, `appointments`, `emergency_contacts`, `caregiver_notes`, `grocery`, `financial`). If parsing fails, the router returns 422 with the raw LLM output. No silent fallback — callers must retry with clearer input.
- Alternative: multi-turn extraction. Rejected — overkill for onboarding text that already contains the data.

**Decision: File ingest reads the entire file into memory, extracts text/image, then follows the same extraction path as `/ingest/text`**
PDFs are read with pdfplumber page-by-page; images are base64-encoded and passed to `call_claude_vision`. Both produce a text string that feeds the same LLM extraction prompt. This keeps the two code paths parallel and easy to test.
- Alternative: stream large files. Rejected — patient onboarding docs are small (<10 pages / <5MB). Memory limit enforced at FastAPI upload size limit.

**Decision: Patient update uses a two-step staged-confirm pattern**
`POST /patients/{id}/update` calls an LLM classifier that returns `domain`, `operation`, `fields_changed`, `summary`, and `proposed_changes` (structured diff). The record is persisted as `confirmed=0, applied=0`. The API responds with `requires_confirmation=true` and the update record. `POST /patients/{id}/update/{update_id}/confirm` calls `apply_patient_update()` then hits `/internal/detect` with `patient_update` trigger and `updated_domain`.
- Alternative: apply immediately on update POST. Rejected — spec requires confirmation step before mutation.

**Decision: `proposed_changes` stored as TEXT JSON in `patient_updates`**
The classifier returns a free-form dict of changes (e.g. `{"medications": [...]}`) which is serialized to JSON. `apply_patient_update` deserializes and passes to `write_patient`. This avoids a per-domain columns explosion.
- Alternative: structured columns per domain. Rejected — too rigid for the LLM output shape.

**Decision: Action chat API route calls executor `/internal/detect` is wrong; instead it POSTs a `ChatMessage` to executor via ASI:One HTTP bridge**
`POST /actions/{id}/chat` retrieves the action for context, writes the user message to `action_chat`, then POST to `EXECUTOR_INTERNAL_URL/message` with the user text augmented with action context. The executor handles it via its `ChatMessage` handler and the DB-backed response is polled or written async. For the MVP, the route writes the user message, forwards to executor `/message`, and returns `{ "status": "queued" }`.
- Alternative: long-poll for executor response. Rejected — adds timeout complexity; the dashboard polls `GET /actions/{id}/chat-history`.

**Decision: CORS middleware uses wildcard origin in dev, configurable via `CORS_ORIGINS` env var**
`CORSMiddleware(app, allow_origins=cors_origins, allow_methods=["*"], allow_headers=["*"])` where `cors_origins = json.loads(os.getenv("CORS_ORIGINS", '["*"]'))`. Production deployments set the env var to the specific dashboard origin.
- Alternative: hardcode localhost:5173. Rejected — breaks staging and production deploys.

## Risks / Trade-offs

- [LLM extraction latency] → `/ingest/text` will take 2–5s per call. Mitigation: document this in the response; add a `processing_time_ms` field to the response envelope.
- [pdfplumber not installed] → `POST /ingest/file` will 500 on PDF uploads. Mitigation: task list includes adding `pdfplumber` and `python-multipart` to requirements.txt; add try/import guard with 501 Not Implemented on ImportError.
- [LLM extraction produces wrong schema] → `write_patient` will silently ignore unknown keys. Mitigation: validate that `patient_id` or `name` is present in the extracted dict before writing; return 422 if neither is extractable.
- [patient_updates.proposed_changes column missing from existing DBs] → `write_patient_update` will fail. Mitigation: schema.sql ALTER is additive; seed.py reset will recreate. Add a migration guard in `get_connection()`.
- [Action chat `/message` proxy requires executor running] → Route returns 502 if executor not reachable. Mitigation: same pattern as existing ingest proxy — check `EXECUTOR_INTERNAL_URL`, return 503 with message if not configured.

## Migration Plan

1. Add `proposed_changes TEXT` column to `patient_updates` in `schema.sql`.
2. Add migration guard in `db.get_connection()` — `ALTER TABLE patient_updates ADD COLUMN proposed_changes TEXT` wrapped in try/except.
3. Update `api/routers/ingest.py` — rewrite `/text`, add `/file`.
4. Update `api/routers/patients.py` — add update pipeline routes.
5. Update `api/routers/actions.py` — add chat, chat-history, dismiss; update approve.
6. Update `api/main.py` — add CORS middleware.
7. Install `pdfplumber python-multipart` into requirements.txt.
8. Re-run `python -m data.seed` to pick up schema change.

Rollback: revert all seven files; re-seed.
