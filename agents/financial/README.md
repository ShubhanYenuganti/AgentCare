# Financial Agents

Financial domain is implemented as supervisor + worker with production detection and question flows.
Modification is explicitly not supported for this domain.

## Components
- `financial-supervisor` (port `8401`)
- `financial-worker` (port `8402`)

## What this domain handles
- Bill deadline and missed-autopay risk detection.
- Spending anomaly signaling from financial context.
- Financial task drafting for caregiver follow-up.
- Question answering over financial life-graph context.

## Message contracts
- Legacy compatibility (optional): `MockDomainTask` path behind `SPRINT2_MOCK_FALLBACK=true`.
- Production detection:
  - `OnDemandDetectionRequest` -> `WorkerResult` -> `SupervisorResult`
- Production modification:
  - `ModificationRequest` returns `ModificationResult(not_supported)`
- Production question:
  - `QuestionRequest` -> `QuestionTask` -> `QuestionApiResult` -> `QuestionAnswer`

## Detection behavior
- Worker runs deterministic checks (due bills, missed autopay, anomaly pressure).
- LLM synthesis adds domain-specific drafts where needed.
- Supervisor validates template-v1 API payload shape + recipient metadata and applies one correction retry.
- Accepted drafts are risk-scored, persisted, and returned to executor.

## Running
```bash
python -m agents.financial.supervisor
python -m agents.financial.worker
```
