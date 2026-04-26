# Grocery Agents

Grocery domain is implemented as supervisor + worker with production detection and question flows.
Modification is explicitly not supported for this domain.

## Components
- `grocery-supervisor` (port `8301`)
- `grocery-worker` (port `8302`)

## What this domain handles
- Grocery delivery continuity and staple reorder detection.
- Dietary conflict and grocery risk checks.
- Grocery/supply action drafting for caregiver execution or API-backed automation.
- Question answering over grocery context.

## Message contracts
- Legacy compatibility (optional): `MockDomainTask` path behind `SPRINT2_MOCK_FALLBACK=true`.
- Production detection:
  - `OnDemandDetectionRequest` -> `WorkerResult` -> `SupervisorResult`
- Production modification:
  - `ModificationRequest` returns `ModificationResult(not_supported)`
- Production question:
  - `QuestionRequest` -> `QuestionTask` -> `QuestionApiResult` -> `QuestionAnswer`

## Detection behavior
- Worker runs deterministic grocery rule checks (delivery staleness, dietary conflicts, reorder cadence).
- Worker can trigger mock grocery ordering helper for rule context.
- LLM pass supplements deterministic output with additional actionable drafts.
- Supervisor enforces API payload template validity, recipient constraints, and exclusivity rules.
- Invalid drafts are corrected once, then dropped if still invalid.

## Running
```bash
python -m agents.grocery.supervisor
python -m agents.grocery.worker
```
