## Context

Sprint 1 completed a validated scaffold with ASI:One chat round-trips and a ten-agent topology, but core runtime behavior remains mock-oriented. The architecture that proved reliable in Sprint 1 differs from earlier assumptions in two important ways: intra-stack hops are short-circuited through `LocalFirstResolver`, and ASI:One traffic enters through executor mailbox ingress while internal flows stay direct and event-driven.

Sprint 2 must productionize supervisors, workers, executor routing, API routers, and dashboard data binding without breaking these proven constraints. The implementation also introduces external dependencies (LLM calls and third-party APIs), which adds timeout, retry, and failure-isolation requirements.

Stakeholders are platform developers (runtime correctness), product operators (action quality/timeliness), and care coordinators (dashboard/API usability).

## Goals / Non-Goals

**Goals:**
- Replace mock task/result flows with production request types and deterministic state transitions.
- Implement executor intent routing (`question`, `modification`, `scheduling`, `detection`) with parallel detection fan-out and bounded aggregation.
- Wire API and dashboard placeholders to live SQLite-backed read/write behavior for key operator workflows.
- Preserve Sprint 1 architecture invariants: executor mailbox ingress for ASI:One, direct local resolver for internal hops, and event-driven supervisors/workers.
- Establish retry, timeout, and fallback behavior for LLM/external API failures without blocking unrelated domain processing.

**Non-Goals:**
- Replacing SQLite with a new persistence engine.
- Introducing additional scheduled loops beyond existing expiration-check cadence.
- Full autonomous optimization/scoring redesign outside sprint-defined action ranking constants.
- Broad UI redesign; Sprint 2 focuses on wiring and operational usability, not visual rebrand.

## Decisions

### Decision 1: Preserve mailbox boundary and local-first routing
- Decision: Keep executor as the only ASI:One ingress/egress boundary while all internal agent-to-agent traffic uses `LocalFirstResolver` when targets are in-stack.
- Rationale: This is the architecture validated in Sprint 1 and eliminates mailbox-induced intra-stack latency while preserving external interoperability.
- Alternative considered: Route all traffic through mailbox for conceptual uniformity.
- Why not: Adds large latency amplification and reintroduces the silent failure modes observed during Sprint 1 chat debugging.

### Decision 2: Intent-first executor orchestration with typed contracts
- Decision: Replace keyword-only routing with a typed intent router that emits production request contracts (`QuestionRequest`, `ModificationRequest`, `SchedulingQuery`, `OnDemandDetectionRequest`).
- Rationale: Sprint 2 requires branching behaviors and multi-domain detection fan-out that keyword-only single-domain routing cannot represent safely.
- Alternative considered: Keep keyword map and patch edge-cases incrementally.
- Why not: Produces brittle branching and duplicated logic in downstream supervisors.

### Decision 3: Supervisor-owned lifecycle, worker-owned enrichment
- Decision: Supervisors own request lifecycle and DB-side action state transitions; workers own LLM/external API enrichment and return normalized outputs.
- Rationale: Keeps orchestration deterministic and confines external variability to worker boundaries.
- Alternative considered: Let workers write directly to DB.
- Why not: Increases race-condition risk and weakens auditability of action lifecycle transitions.

### Decision 4: API/dashboard contract stabilization before breadth expansion
- Decision: Prioritize canonical API envelopes and dashboard route parity for Actions/Patients/Caregivers/Org/Notifications before adding ancillary features.
- Rationale: Sprint 2 success depends on operational visibility and stable contracts, not feature breadth.
- Alternative considered: Parallelize all feature work and defer contract stabilization.
- Why not: Raises rework risk when UI and agent outputs drift.

### Decision 5: Bounded failure handling with partial progress
- Decision: Use per-domain timeout budgets, retries for transient external failures, and partial aggregation semantics (successful domains still return) for detection workflows.
- Rationale: Prevents one failing domain from collapsing full multi-domain responses.
- Alternative considered: All-or-nothing aggregation.
- Why not: Reduces availability and operator trust when dependencies are flaky.

## Risks / Trade-offs

- [Increased operational complexity from external APIs and LLMs] -> Mitigation: domain-level timeout/retry policy, structured error codes, and executor fallback messaging.
- [Schema/model drift between agents and API/dashboard] -> Mitigation: shared typed contracts in `agents/shared/models.py`, integration tests on API envelope and action transitions.
- [Latency regression under parallel detection] -> Mitigation: maintain local-first routing, cap fan-out concurrency, and set aggregation deadlines.
- [Overwriting validated Sprint 1 behavior while refactoring] -> Mitigation: add regression tests for mailbox ingress, direct internal routing, and no-interval supervisor behavior before broad rewrites.
- [Partial delivery semantics may confuse users] -> Mitigation: include per-domain completion/error metadata in responses and dashboard activity logs.

## Migration Plan

1. Lock Sprint 1 baseline with regression tests for executor chat ingress, internal routing path, and current health endpoints.
2. Introduce production request/result contracts in shared models with adapter shims to preserve interim compatibility.
3. Implement executor intent router and detection fan-out aggregator behind feature flags/config toggles.
4. Migrate supervisors/workers domain by domain from mock handlers to production flows.
5. Wire API routes to shared DB helpers and expose stable response envelopes.
6. Bind dashboard routes to live endpoints, add loading/error states, and validate route parity.
7. Remove mock-only pathways once production path passes integration/E2E checks.
8. Rollback strategy: retain ability to switch executor to mock routing mode and disable external integrations via env toggles while preserving API read access.

## Resolved Questions

### Detection fan-out domain filtering
- **Decision:** Executor pre-filters domains when the trigger is a patient *update* (existing patient record mutated). Uses the updated fields to select only affected domains (e.g. medication change → health + financial; schedule change → appointment + grocery). When trigger is patient *initiation/creation*, bypass pre-filter entirely and fan out to all domains — no prior state exists to score against.
- **Rationale:** New patients have no domain history; any domain could be relevant. Existing patients have a known Life Graph; filtering avoids unnecessary LLM calls.

### Per-domain timeout budget
- **Decision:** 5 minutes (300 s) per domain for Sprint 2. Applied uniformly across ASI:One chat and dashboard-triggered workflows. Partial aggregation (Decision 5) ensures responding domains surface results before the budget expires.
- **Rationale:** LLM + external API chains can be slow; 5 min is conservative but safe for Sprint 2 operational testing. Tighten in Sprint 3 once latency baselines are measured.

### External API requirements
- **Required (explicit implementation tasks):**
  - `ANTHROPIC_API_KEY` — LLM calls in all domain workers; blocking dependency.
  - `RESEND_API_KEY` — notification delivery; blocking dependency.
- **Deferred to Sprint 3:**
  - `GOOGLE_MAPS_API_KEY` — not needed in Sprint 2 scope.
  - Other provider keys (Instacart, OpenFDA, Amazon) — implement only if credentials are available and spec explicitly targets them in Sprint 2.

### Idempotency keys on modification requests
- **Decision:** Yes. All `ModificationRequest` submissions at the API boundary must include a client-supplied idempotency key. The API layer checks for an existing result keyed on that ID before processing; duplicate submissions return the prior result without re-executing the pipeline.
- **Rationale:** Modification requests mutate DB state and may trigger external API calls; retries without idempotency create duplicate actions.
