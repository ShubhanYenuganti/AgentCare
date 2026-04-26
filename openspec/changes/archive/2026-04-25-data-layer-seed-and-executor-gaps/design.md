## Context

The Sprint 1 codebase stores all patient domain data as a JSON blob in `patients.life_graph_json`. This was a scaffold shortcut. The spec defines normalized relational tables for medications, appointments, grocery, grocery_staples, financial_bills, financial_anomalies, emergency_contacts, and caregiver_notes. Domain workers need to read these tables directly (not parse a blob) to execute deterministic detection checks (refill-due arithmetic, adherence gap counting, appointment overdue calculation, bill due-date comparison). The executor also needs a `/internal/detect` HTTP endpoint so the FastAPI layer (ingest, patient-update confirm) can fire the agent fan-out synchronously over localhost.

## Goals / Non-Goals

**Goals:**
- Replace blob storage with fully normalized life-graph tables matching the spec schema exactly.
- Rewrite `serialize_life_graph` to JOIN across normalized tables and return the dict structure domain workers expect.
- Rewrite `seed.py` with the full spec patient dataset (3 patients, complete domain records, adherence logs, anomalies).
- Add `action_history` columns missing from Sprint 1: `completion_date`, `assigned_caregiver`, `caregiver_options_json`, `outcome`.
- Add `expiration_notifications.notified_at` column.
- Implement `POST /internal/detect` on executor and fix org context injection in `run_detection()`.
- Add `get_latest_pending_scheduling_action(requester_address)` DB helper used by scheduling agent chat flow.

**Non-Goals:**
- Domain worker detection logic (Sprint 2 task 4 items) — this change only guarantees the data they need is present.
- Dashboard or API contract changes.
- Migration of any existing production data (dev/demo only).

## Decisions

**Decision: Drop denormalized columns from `patients` table**
The columns `pharmacy_name`, `pharmacy_email`, `doctor_name`, `doctor_email`, `life_graph_json` are Sprint 1 scaffolding. They encode data that now belongs in `medications` and `appointments` tables respectively. Keeping both would create two sources of truth.
- Alternative: keep blob as cache alongside normalized tables. Rejected — adds sync complexity for zero benefit in this codebase.

**Decision: `serialize_life_graph` returns a dict matching spec Section 3.3 patient structure exactly**
Workers do `patient["medications"]`, `patient["appointments"]`, etc. The returned dict must have these keys at the top level. The function does one DB round-trip per call using a single connection, reading each normalized table with a simple WHERE patient_id=? query.
- Alternative: return ORM-style nested objects. Rejected — spec defines a plain dict contract.

**Decision: `write_patient` writes to normalized tables, not blob**
During ingest/onboarding, the LLM returns a structured dict. `write_patient` upserts the core `patients` row and fans out sub-lists (medications, appointments, etc.) to their respective tables. Any sub-item without an explicit `med_id`/`appt_id` gets a generated UUID.
- Alternative: continue writing blob, migrate lazily. Rejected — breaks detection checks immediately.

**Decision: Schema migration is destructive (drop+recreate)**
`seed.py` drops the DB and rebuilds from scratch. This is a demo/dev project; no migration scripts needed.

**Decision: `/internal/detect` is implemented as a uagents `on_rest_post` handler, not a separate FastAPI sub-app**
The endpoint is registered via `@executor.on_rest_post("/internal/detect", ...)` which runs natively within the uagents event loop. No `asyncio.run_coroutine_threadsafe` bridge is needed — the handler directly calls `_dispatch_detection()` as a regular async function. A `_executor_ready` flag (set in the startup handler) guards against calls before agent initialization completes, returning HTTP 503 if not ready.
- Alternative: separate FastAPI process with `asyncio.run_coroutine_threadsafe` bridge. Rejected — uagents REST handlers already run in the agent's event loop; a bridge adds complexity with no benefit.

## Risks / Trade-offs

- [Schema change removes `patients.life_graph_json`] → Any code still reading that column breaks. Audit all callers of `get_patient()` and `serialize_life_graph()` before committing. Mitigation: grep for `life_graph_json` and `pharmacy_name` / `doctor_name` in db.py callers.
- [seed.py full rewrite loses old seed state] → Dev DB must be re-seeded after merge. Mitigation: document in README; seed is idempotent (deletes and recreates).
- [`_executor_ready` guard for /internal/detect] → Handler raises HTTP 503 if called before the startup event fires. FastAPI ingest/update routers should retry on 503 with backoff. The `_executor_ready` flag is set in `@executor.on_event("startup")` so it is true as soon as the agent loop is running.

## Migration Plan

1. Update `data/schema.sql` — add new tables, add missing columns to `action_history` and `expiration_notifications`, remove denormalized columns from `patients`.
2. Update `agents/shared/db.py` — new helpers, updated `serialize_life_graph`, updated `write_patient`, updated `apply_patient_update`.
3. Update `data/seed.py` — full rewrite with spec patient data.
4. Add `/internal/detect` to executor and fix org context injection.
5. Re-seed: `python -m data.seed` (drops and recreates DB).
6. Run existing tests to verify no regressions.

Rollback: revert all four files; re-run seed with prior version.
