# Appointment Agents

Appointment domain is implemented as supervisor + worker with production detection and question flows.
Modification is explicitly not supported for this domain.

## Components
- `appointment-supervisor` (port `8201`)
- `appointment-worker` (port `8202`)

## What this domain handles
- Appointment and transport-oriented detection actions.
- Rule-assisted checks for overdue/near-term visits.
- Scheduling/visit-prep drafts with caregiver-facing instructions.
- Question answering over appointment context.

## Message contracts
- Legacy compatibility (optional): `MockDomainTask` path behind `SPRINT2_MOCK_FALLBACK=true`.
- Production detection:
  - `OnDemandDetectionRequest` -> `WorkerResult` -> `SupervisorResult`
- Production modification:
  - `ModificationRequest` returns `ModificationResult(not_supported)`
- Production question:
  - `QuestionRequest` -> `QuestionTask` -> `QuestionApiResult` -> `QuestionAnswer`

## Detection behavior
- Supervisor parses domain-specific snapshot context before worker dispatch.
- Worker performs rule checks (including overdue/upcoming appointment signals) and LLM synthesis.
- Worker may call mock calendar availability (`/mock/cal/available`) and gmaps helper for travel context.
- Supervisor validates API payload templates and recipient metadata, with one correction retry.
- Valid drafts are risk-scored, persisted, and returned to executor.

## Running
```bash
python -m agents.appointment.supervisor
python -m agents.appointment.worker
```
