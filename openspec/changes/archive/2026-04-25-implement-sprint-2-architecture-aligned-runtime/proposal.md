## Why

Sprint 1 validated end-to-end ASI:One chat delivery and multi-agent routing, but the runtime is still scaffold-level with mock contracts and placeholder API/dashboard behavior. Sprint 2 is needed now to convert the validated topology into production behavior while preserving the architectural decisions proven in Sprint 1 (executor mailbox ingress plus local-first intra-stack routing).

## What Changes

- Replace mock supervisor/worker processing with production request flows for detection, modification, and question handling.
- Upgrade executor routing from keyword-only classification to explicit intent routing with domain fan-out for detection workflows.
- Wire FastAPI routes and dashboard views to real SQLite-backed data and action lifecycle updates.
- Add domain worker integrations for LLM-backed analysis and live external API enrichment where required by the product spec.
- Codify Sprint 1 architecture constraints into spec requirements so Sprint 2 implementation does not regress mailbox and routing behavior.

## Capabilities

### New Capabilities
- `production-domain-runtime`: Implement supervisor/worker production request handling, DB writes, and deterministic result contracts replacing mock-only processing.
- `executor-intent-detection-orchestration`: Implement executor-level intent routing and parallel detection orchestration across domain supervisors with resilient aggregation.
- `api-dashboard-live-data`: Implement API endpoint and dashboard integration against live action, patient, caregiver, scheduling, and notification data.
- `domain-live-integration-workers`: Implement domain worker LLM/tooling integration for detection, modification support, and external API enrichment.

### Modified Capabilities
- `quickstarter-multiagent-scaffold`: Update requirements to preserve Sprint 1 architectural constraints during productionization (LocalFirstResolver for intra-stack hops, executor as ASI:One mailbox ingress, no supervisor interval loops).
- `foundation-runtime-bootstrap`: Update requirements to reflect migration from scaffold placeholders to production-wired API/dashboard behavior while preserving existing runtime contracts and seed invariants.

## Impact

- Affected code: `agents/executor/*`, `agents/*/{supervisor,worker}.py`, `agents/shared/{models.py,db.py,llm.py,state_service.py,constants.py}`, `agents/scheduling/agent.py`, `api/routers/*`, `dashboard/src/*`.
- Affected behavior: message schemas, orchestration flow, database write/read paths, API responses, dashboard rendering, and external integration error handling.
- Operational impact: adds LLM/external API dependencies and increases need for retries, timeout handling, and observability on worker and executor paths.
- Testing impact: requires expanded unit/integration/E2E coverage for intent routing, parallel domain execution, API contracts, and UI-data parity.
