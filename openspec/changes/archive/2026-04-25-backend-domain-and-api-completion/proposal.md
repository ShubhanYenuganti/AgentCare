## Why

The MACOS agent system has a working foundation (Sprint 1–2) but all four domain supervisors/workers use generic LLM-only detection, the scheduling agent is mock-only, the FastAPI contract is missing bulk of spec-defined endpoints, and mock API parity is unverified. Without this work, the system cannot demonstrate deterministic, spec-aligned care operations.

## What Changes

- Replace generic LLM detection in all four domain workers with explicit spec-defined rule checks (health refill/dose/OpenFDA, appointment transport/visit-prep, grocery staleness/dietary/supply, financial bill-due/autopay/anomaly)
- Implement OpenFDA live integration (interaction + recall) with timeout/retry/fallback in the health worker
- Add Google Maps Distance Matrix integration in the appointment worker for transport planning
- Add supervisor risk-scoring LLM reassessment pass across all domains
- Implement spec-aligned modification pipeline for health domain (live-data aware, review pass, retry, changes summary)
- Implement spec-aligned question pipeline branching (`question_requires_live_api`) for all domains
- Enforce non-health domains return "not supported yet" for modification requests
- Replace mock-only scheduling agent with full `SchedulingQuery` flow: options generation, chat-selection handler, caregiver assignment, slot booking, escalation on decline
- Add scheduling router endpoints: `POST /scheduling/{id}/assign`, `POST /scheduling/{id}/confirm`, `POST /scheduling/{id}/decline`
- Add FastAPI contract gaps: CORS middleware, enriched `GET /patients`, `GET /patients/{id}`, `GET /actions` with filtering, caregiver schedule/assignment endpoints, org `PUT` support
- Align mock API response contracts to spec snapshots; add coverage tests for all mock endpoints
- Complete remaining executor gaps: intent handler surface (onboarding, scheduling-query, action-bound flows, general query fallback)
- Soft-delete support (`active=0`) for removal operations across all normalized life-graph tables

## Capabilities

### New Capabilities

- `health-domain-detection`: Spec-defined health detection rules — refill due, missed-dose+worsening, OpenFDA interaction, OpenFDA recall
- `appointment-domain-detection`: Overdue appointment, Google Maps transport planning, visit prep, post-visit extraction
- `grocery-domain-detection`: Delivery staleness, dietary conflict, supply reorder with cart/order mock API calls
- `financial-domain-detection`: Bill due alert, missed autopay, anomaly detection using life-graph financial history
- `domain-modification-question-pipelines`: Health modification live-data path + all-domain question live-API branching
- `scheduling-agent-workflow`: Full scheduling query → options → chat-selection → assignment → confirm/decline lifecycle
- `scheduling-api`: `/scheduling/{id}` assign/confirm/decline REST endpoints
- `fastapi-contract-completion`: Enriched patient/action endpoints, CORS, caregiver schedule, org PUT alignment
- `mock-api-coverage`: Verified mock route payload/response contracts with coverage tests
- `executor-intent-surface`: Onboarding, scheduling-query, action-bound modification/question, general query fallback with DB context

### Modified Capabilities

- `executor-intent-detection-orchestration`: Soft-delete on removal ops; intent handler surface fully aligned to spec workflow
- `production-domain-runtime`: Risk-scoring reassessment pass added to all four supervisors; cross-domain modification guard

## Impact

- `agents/domains/*/supervisor.py` — risk-scoring pass, modification guard, live-API branching
- `agents/domains/*/worker.py` — explicit spec rule checks replace generic LLM generation
- `agents/domains/health/` — OpenFDA client, modification pipeline with review/retry
- `agents/domains/appointment/` — Google Maps client, scheduling-task output structure
- `agents/scheduling/agent.py` — full SchedulingQuery flow replaces MockDomainTask
- `agents/executor/agent.py` — intent handler surface completion
- `api/routers/` — patients, actions, scheduling, caregivers, org routers updated
- `api/mock/` — mock route contracts aligned, coverage tests added
- `data/schema.sql` + `agents/shared/db.py` — soft-delete support
- No `dashboard/` files touched
