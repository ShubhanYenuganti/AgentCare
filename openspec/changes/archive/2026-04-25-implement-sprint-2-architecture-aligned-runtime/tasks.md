## 1. Baseline Guardrails

- [x] 1.1 Add regression tests that lock Sprint 1 architecture invariants (executor mailbox ingress, LocalFirstResolver in-stack routing, event-driven supervisors without interval handlers)
- [x] 1.2 Add regression tests for executor chat acknowledgement plus correlated final reply behavior
- [x] 1.3 Capture current mock-path behavior snapshots to compare against Sprint 2 migration outcomes

## 2. Shared Contracts and Lifecycle Foundations

- [x] 2.1 Extend `agents/shared/models.py` with production request/result contracts and compatibility adapters
- [x] 2.2 Implement/verify deterministic action lifecycle transition validation in shared services
- [x] 2.3 Update `agents/shared/state_service.py` request correlation and timeout cleanup semantics for multi-domain fan-out

## 3. Executor Intent and Detection Orchestration

- [x] 3.1 Implement intent classification (`question`, `modification`, `scheduling`, `detection`) in executor routing flow
- [x] 3.2 Implement detection fan-out with patient-lifecycle-aware domain selection: full fan-out on patient create/initiation; field-based domain pre-filter on patient update; 300 s per-domain timeout with partial aggregation
- [x] 3.3 Preserve and test executor-only mailbox ingress/egress with immediate chat acknowledgement behavior
- [x] 3.4 Add executor-level structured error mapping for timeout, validation, and downstream failure classes

## 4. Domain Supervisor and Worker Productionization

- [x] 4.1 Migrate health supervisor/worker from mock handlers to production request flows and typed outputs
- [x] 4.2 Migrate appointment supervisor/worker from mock handlers to production request flows and typed outputs
- [x] 4.3 Migrate grocery supervisor/worker from mock handlers to production request flows and typed outputs
- [x] 4.4 Migrate financial supervisor/worker from mock handlers to production request flows and typed outputs
- [x] 4.5 Implement supervisor-owned persistence and audit updates for detection/modification/question workflows

## 5. Domain External Integrations and Resilience

- [x] 5.0a **[REQUIRED — blocking]** Verify `ANTHROPIC_API_KEY` is present in `.env` and wired through `agents/shared/llm.py`; all LLM worker calls depend on this
- [x] 5.0b **[REQUIRED — blocking]** Verify `RESEND_API_KEY` is present in `.env` and wired into the notification delivery layer; action/modification notifications depend on this
- [x] 5.1 Wire `call_claude()`-based enrichment into worker flows with schema validation and parse-repair handling
- [x] 5.2 Add required third-party API clients with timeout/retry/fallback policy per domain (`GOOGLE_MAPS_API_KEY` deferred to Sprint 3)
- [x] 5.3 Ensure worker boundary input validation and structured failure payloads for invalid tasks and provider failures

## 6. API Live Data Wiring

- [x] 6.1 Replace placeholder route handlers in `api/routers/*` with live SQLite-backed reads/writes via shared DB helpers
- [x] 6.1a Enforce idempotency keys on all `ModificationRequest` endpoints: check for existing result by key before processing; return prior result on duplicate
- [x] 6.2 Enforce consistent API response envelope (`success`, `data`, `error`) across Sprint 2 endpoints
- [x] 6.3 Add API integration tests for actions, patients, caregivers, scheduling, notifications, and modification flows (including duplicate-key idempotency assertions)

## 7. Dashboard Live Contract Integration

- [x] 7.1 Wire Actions route to live API data with loading, empty, and error states
- [x] 7.2 Wire Patients and Caregivers routes to live API contracts with parity to backend schemas
- [x] 7.3 Wire Org and Notifications surfaces to live runtime data and mutation flows where applicable
- [x] 7.4 Add dashboard integration/E2E tests for top-level route data rendering and failure handling

## 8. Verification, Security, and Cutover

- [x] 8.1 Add end-to-end tests covering ASI:One chat ingress through production orchestration to final response
- [x] 8.2 Perform security review checks (input validation, secret handling, error redaction, external call hardening)
- [x] 8.3 Remove or gate obsolete mock-only execution paths after production path passes tests
- [x] 8.4 Run full verification loop (unit, integration, E2E, compile/type/lint checks) and record Sprint 2 readiness evidence
