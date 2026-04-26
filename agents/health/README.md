# Health Agents

Health domain is implemented as supervisor + worker and is the only domain that supports end-to-end modification in the current policy.

## Components
- `health-supervisor` (port `8101`)
- `health-worker` (port `8102`)

## What this domain handles
- Detection drafts for medication/refill/safety workflows.
- Deterministic rule checks before LLM synthesis (refill windows, adherence risk, interaction/recall checks).
- Question answering against patient life-graph context.
- Modification pipeline for health actions.

## Message contracts
- Legacy compatibility (optional): `MockDomainTask` -> `MockWorkerResult` -> `MockSupervisorResult`
  - gated by `SPRINT2_MOCK_FALLBACK=true`.
- Production detection:
  - `OnDemandDetectionRequest` -> worker
  - `WorkerResult` -> supervisor
  - `SupervisorResult` -> executor
- Production modification:
  - `ModificationRequest` -> `ModificationTask` -> `ModificationDraft` -> `ModificationResult`
- Production question:
  - `QuestionRequest` -> `QuestionTask` -> `QuestionApiResult` -> `QuestionAnswer`

## Detection behavior
- Supervisor filters snapshot context for health-relevant fields.
- Worker runs deterministic rule checks and LLM synthesis.
- Supervisor enforces action-type exclusivity and API payload validation.
- Invalid API drafts trigger one correction retry before dropping invalid drafts.
- Valid drafts are persisted via `write_action` and returned to executor.

## External capability hooks
- Mock pharmacy availability lookup (`/mock/cvs/available`) for context enrichment.
- OpenFDA checks in worker (`interaction`, `recall`) for safety/risk augmentation.

## Running
```bash
python -m agents.health.supervisor
python -m agents.health.worker
```
