## Why

The current data layer uses a flat `life_graph_json` blob on the `patients` table instead of the normalized relational tables defined in the spec (medications, appointments, grocery, financial_bills, etc.), so domain workers cannot perform the deterministic rule-based checks the spec requires. The executor also lacks the `POST /internal/detect` endpoint that connects the FastAPI ingest/update pipeline to the agent detection fan-out.

## What Changes

- **Schema**: Add missing normalized life-graph tables (`emergency_contacts`, `medications`, `caregiver_notes`, `appointments`, `grocery`, `grocery_staples`, `financial_bills`, `financial_anomalies`) and add missing columns to `action_history` (`completion_date`, `assigned_caregiver`, `caregiver_options_json`, `outcome`) and `expiration_notifications` (`notified_at`).
- **seed.py**: Fully rewrite to populate all normalized tables with the complete spec-defined patient data (3 patients with full medication, appointment, grocery, and financial records, including the anomalies and adherence logs needed for detection checks).
- **db.py `serialize_life_graph`**: Replace blob-only implementation with a proper JOIN-based assembly from normalized tables, returning the full life graph dict the spec defines.
- **db.py new helper**: Add `get_latest_pending_scheduling_action(requester_address)` for the scheduling agent chat-selection flow.
- **Executor `POST /internal/detect`**: Implement the internal HTTP endpoint that calls `run_detection()` from FastAPI context, enabling ingest and patient-update flows to trigger the agent fan-out.
- **Executor `run_detection()`**: Fix fan-out to inject domain-specific org context using `ORG_CONTEXT_MAP` (currently sends empty dict).

## Capabilities

### New Capabilities

- `normalized-life-graph`: Full normalized SQLite schema for all life-graph domains and the `serialize_life_graph` DB helper that builds the spec-compliant dict from those tables.
- `deterministic-seed-data`: Complete seed dataset with all per-patient domain records (medications with adherence logs, appointments, grocery staples, financial bills/anomalies) that supports all domain detection checks.
- `executor-internal-detect`: `POST /internal/detect` HTTP endpoint on the executor agent that bridges FastAPI ingest/update routes to the uagents detection fan-out.

### Modified Capabilities

- `foundation-runtime-bootstrap`: Schema and seed are part of the foundation runtime; this change replaces the blob-based patient storage with normalized tables, which is a requirements-level change to what the DB layer provides.

## Impact

- `data/schema.sql`: New tables added; `patients` table loses denormalized fields (`pharmacy_name`, `pharmacy_email`, `doctor_name`, `doctor_email`, `life_graph_json`); those fields move into normalized tables.
- `data/seed.py`: Full rewrite.
- `agents/shared/db.py`: `serialize_life_graph`, `write_patient`, `apply_patient_update`, `get_all_patients`, `get_patient` updated for normalized schema; new `get_latest_pending_scheduling_action` added.
- `agents/executor/agent.py`: `run_detection()` org context injection fixed; `/internal/detect` FastAPI endpoint added.
- All domain workers depend on `serialize_life_graph` output — format change is immediately upstream of detection checks.
