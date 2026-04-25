# MACOS Context

Last updated: April 25, 2026

This document is the current implementation context for MACOS and replaces the prior Sprint 1-only runbook. It is structured in the requested order:

1. Current capabilities overlay (detailed)
2. Change log against Sprint 1 baseline
3. Change log against original Sprint 2 plan

## 1) Current Capabilities Overlay

### 1.1 Runtime topology and execution model

- Agent stack is running as a 10-process topology:
  - `executor`
  - `health-supervisor`, `health-worker`
  - `appointment-supervisor`, `appointment-worker`
  - `grocery-supervisor`, `grocery-worker`
  - `financial-supervisor`, `financial-worker`
  - `scheduling-agent`
- ASI:One/chat boundary remains executor-only mailbox ingress/egress.
- Intra-stack routing remains local-first through `LocalFirstResolver` (`/submit` direct local HTTP).
- Supervisors are event-driven handlers (no domain polling loops).
- Executor still runs timeout/heartbeat loops for orchestration safety and fan-out cleanup.

### 1.2 Executor intent routing and orchestration

Executor supports `question`, `modification`, `scheduling`, and `detection` intents.

- `question`:
  - Routes to domain supervisor (domain from classifier, fallback `health`).
- `modification`:
  - Routes to domain supervisor with `ModificationRequest`.
- `scheduling`:
  - Routes to `scheduling-agent` via mock contract path.
- `detection`:
  - Performs patient resolution and life-graph snapshot preparation.
  - Fans out to selected domains.
  - Aggregates partial results with per-domain timeout metadata.

Intent classification:

- Primary: LLM JSON classifier.
- Fallback: keyword classifier.

Timeout policies:

- Request timeout: 45 seconds for normal pending request state.
- Detection domain timeout budget: 300 seconds per fan-out pass.

### 1.3 Detection targeting and patient resolution

Detection now supports patient targeting beyond `patient_id` regex only.

- For `patient_create` trigger:
  - Bypasses name resolution.
  - Uses provided/extracted `patient_id` or creates `pt_create_<pass>` synthetic id.
  - Uses full DB life graph if present, else bootstraps a complete life-graph envelope.
- For `patient_update` trigger:
  - Resolution order:
    - explicit `patient_id` if provided and active
    - name extraction via `find_active_patients_by_name_query(query)`
  - Name lookup supports unique partial matches (for example `Margaret`), and blocks when ambiguous.
  - If no unique active patient match is found, detection is blocked with a validation response.

### 1.4 Life-graph snapshot strategy

Detection uses complete patient life graph as source snapshot, then domain-specific slicing.

- Executor snapshot source:
  - Full snapshot from `serialize_complete_life_graph(patient_id)`.
  - Snapshot metadata includes key list, byte size, source, generation timestamp.
- Supervisor handling:
  - Reads full snapshot.
  - Parses/truncates to domain-relevant JSON via `parse_life_graph_for_domain`.
  - Passes only `domain_patient_context` to worker.
- Domain parser behavior:
  - Top-level allowlist per domain.
  - Domain filter for `actions`, `patient_updates`, `action_chat`, `notifications`, `expiration_notifications`.
  - `caregiver_schedule` retained only for appointment domain.

### 1.5 Detection fan-out domain selection

- `patient_create` -> full fan-out: `health`, `appointment`, `grocery`, `financial`.
- `patient_update` -> field-based pre-filter using `_FIELD_DOMAIN_MAP` (fallback to all if no mapped field hit).

### 1.6 Supervisor behavior in production paths

All four domain supervisors (`health`, `appointment`, `grocery`, `financial`) now implement:

- Detection handling:
  - receive `OnDemandDetectionRequest`
  - parse domain life-graph context
  - forward to worker
  - validate worker drafts for API template requirements
  - issue one correction retry when payload validation fails (`detection_correction` metadata)
  - drop invalid drafts after retry budget
  - persist valid drafts with `write_action`
  - return `SupervisorResult` to executor
- Modification handling:
  - set `modification_in_progress`
  - route `ModificationTask` to worker
  - persist updated draft via `replace_draft`
  - return `ModificationResult`
- Question handling:
  - build question task with patient life-graph lookup context
  - route `QuestionTask` to worker
  - return `QuestionAnswer`

### 1.7 Worker behavior and domain detection capabilities

All domain workers use LLM-backed detection prompts plus API capability guidance from `agents/shared/api_capabilities.py`.

Health worker detection:

- Focus: medications, refill risks, monitoring/safety.
- Calls mock GET lookup before drafting:
  - `GET /mock/cvs/available`
- Produces draft JSON with:
  - urgency tier
  - optional API-executable `manual_action_type`
  - required template-v1 `api_payload` for executable actions
  - `recipient_email`, `recipient_type`

Appointment worker detection:

- Focus: transport, clinic visits, caregiver scheduling, check-ins.
- Calls mock GET lookup before drafting:
  - `GET /mock/cal/available` (patient filtered)
- Produces template-v1 API payloads for booking/availability routes where applicable.

Grocery worker detection:

- Focus: grocery delivery coverage, diet mismatch, food safety, weekly planning.
- Uses domain-scoped life-graph context + API guidance block.
- Produces template-v1 payloads for grocery/supply execution routes where applicable.

Financial worker detection:

- Focus: bill deadlines, autopay opportunities, insurance/benefit gaps, assistance programs.
- Uses domain-scoped life-graph context + API guidance block.
- Produces template-v1 payloads only when it identifies concrete executable actions.

Common worker behavior:

- Supports correction metadata sent from supervisors to repair invalid API payloads.
- Falls back to stub draft when LLM is unavailable or parsing fails.
- Uses structured `[RECV]/[PARSE]/[LLM-CALL]/[LLM-RESULT]/[SEND]` logs.

### 1.8 API payload contract for executable actions

The executable payload contract has shifted from freeform request JSON to template-v1 structured parameter nodes.

Template shape:

```json
{
  "template_version": "v1",
  "call": {
    "route_key": "POST /mock/... or POST resend:/emails",
    "provider": "mock or live",
    "parameters": {
      "field_name": {"value": "..."}
    }
  }
}
```

Behavior:

- Workers are prompted to fill `parameters.<field>.value` instead of generating raw POST body JSON.
- Approve flow extracts parameter nodes and deterministically builds final POST bodies.
- Validator enforces required params plus `recipient_email` and `recipient_type` on API-completable drafts.

### 1.9 Action approval execution path

`POST /actions/{action_id}/approve` now executes API steps instead of render-only behavior.

Execution planner currently supports:

- Mock POST execution from inferred route and extracted template params.
- Optional Google Maps Distance Matrix call when enabled and route/domain qualify.
- Resend email notification execution when recipient email exists.

Success/failure semantics:

- Required-step failures return 502 with execution detail.
- Execution metadata is merged into stored `api_payload.approval_execution`.
- Successful required steps mark action completed and reviewed.

### 1.10 Mock API surface currently implemented

Implemented mock calls:

- `GET /mock/cvs/available`
- `POST /mock/cvs/refill`
- `GET /mock/cal/available`
- `POST /mock/cal/book`
- `POST /mock/instacart/cart`
- `POST /mock/amazon/order`
- `POST /mock/amazon/reorder` (alias)
- `POST /mock/caregivers/available`

Notes:

- `POST /mock/caregivers/available` queries SQLite caregiver schedule + assignments and includes fallback date scanning.
- `GET` mock lookups are wired into detection prompts where currently available in worker implementations.

### 1.11 FastAPI and dashboard current state

FastAPI:

- Mounted routers: `actions`, `patients`, `caregivers`, `scheduling`, `notifications`, `ingest`, `org`, and `mock`.
- Most business endpoints now use shared SQLite helpers and standard envelope `{success,data,error}`.

Dashboard:

- React Router views for Actions, Patients, Caregivers, Org are wired to live API reads.
- Loading, empty, and error states are implemented.
- UI remains functional/minimal (not full design-sprint polish).

### 1.12 Data layer state

SQLite data layer includes:

- deterministic schema/seed baseline from Sprint 1
- complete life-graph serializer for executor/supervisor detection flows
- action lifecycle persistence helpers
- ranking helpers for action feed ordering
- caregiver availability/scheduling support helpers

### 1.13 Test coverage focus areas

Current tests explicitly cover:

- Sprint 1 architecture regressions
- intent routing and detection fan-out logic
- complete life-graph serialization and domain parser behavior
- name-query patient resolution including unique partial matches and ambiguity
- API capability template validation and extraction
- mock API route behavior
- approve success/failure response behavior

## 2) Change Log Against Sprint 1 Baseline

Sprint 1 baseline was scaffold + mock topology. The current system has moved significantly beyond that baseline.

### 2.1 Orchestration and intent

- Sprint 1: keyword-to-domain mock routing.
- Current: intent-first routing with typed request flows and detection fan-out aggregation.

### 2.2 Detection trigger handling

- Sprint 1: scaffold-only mock detection semantics.
- Current:
  - `patient_create` and `patient_update` detection paths are implemented.
  - `patient_create` bypasses name detection and uses full/bootstrap life graph.
  - `patient_update` resolves by active patient ID or unique full/partial name query.

### 2.3 Life-graph usage

- Sprint 1: serializer existed, not used as domain-scoped detection contract.
- Current:
  - executor sends complete life graph snapshot
  - supervisors parse full snapshot into domain-relevant context
  - workers receive scoped JSON only (`domain_patient_context`)

### 2.4 Domain worker execution

- Sprint 1: workers returned deterministic mock strings.
- Current:
  - workers run LLM-based detection/modification/question flows
  - return typed outputs (`ActionDraft`, `ModificationDraft`, `QuestionApiResult`)
  - include API execution fields for actionable drafts

### 2.5 Supervisor responsibilities

- Sprint 1: forward/return mock roundtrip.
- Current:
  - supervisors own persistence and lifecycle handling
  - API payload validation + correction retry is implemented
  - invalid drafts are dropped with explicit logging

### 2.6 API behavior

- Sprint 1: most routers were placeholders.
- Current:
  - actions/patients/caregivers/scheduling/notifications/org use live SQLite helpers
  - approve endpoint executes mock/live calls and records execution metadata
  - standardized response envelopes are used broadly

### 2.7 Mock provider ecosystem

- Sprint 1: mock provider layer not functionally integrated.
- Current:
  - multiple mock GET/POST routes implemented and tested
  - workers and approve path use these routes for detection context and action execution

### 2.8 Agent prompting and API contract quality

- Sprint 1: no structured API payload contract.
- Current:
  - unified route catalog in `agents/shared/api_capabilities.py`
  - template-v1 payload schema enforced
  - workers receive domain API guidance plus global template catalog

### 2.9 Observability and logging

- Sprint 1: scaffold logging.
- Current:
  - verbose lifecycle logs across executor/supervisors/workers/approve flow
  - explicit parse/route/validate/send markers
  - correction and drop outcomes are logged with pass/action identifiers

## 3) Change Log Against Original Sprint 2 Plan

Original Sprint 2 plan is the OpenSpec change set at:

- `openspec/changes/implement-sprint-2-architecture-aligned-runtime/`

The current implementation both fulfills major Sprint 2 goals and adds post-plan upgrades.

### 3.1 Items implemented from original Sprint 2 intent

- Production contracts and typed flows are in place for detection, modification, and question paths.
- Executor intent classification and bounded detection fan-out are implemented.
- Partial-success fan-out aggregation behavior is implemented.
- Supervisors and workers for all four domains are productionized relative to mock baseline.
- API routes are live-wired for core domains and use shared envelope patterns.
- Dashboard routes consume live APIs with loading/empty/error states.
- Sprint 1 architecture guardrails remain preserved:
  - executor mailbox boundary
  - local-first in-stack routing
  - event-driven supervisors

### 3.2 Post-plan upgrades beyond original Sprint 2 text

These upgrades were layered after original Sprint 2 definition and are now part of current baseline.

- Name-resolved detection targeting:
  - active patient lookup from query text
  - unique partial-name support
  - ambiguity blocking with explicit feedback
- `patient_create` detection bypass path:
  - no name resolution required
  - bootstrap life graph generation when DB graph absent
- Full-to-domain life-graph handoff model:
  - executor sends full snapshot
  - supervisors parse/truncate and pass scoped JSON to workers
- Structured template-v1 API payload approach:
  - workers fill parameter nodes
  - approve endpoint extracts and builds deterministic request body
- Expanded mock API catalog including GET enrichment and Amazon order support.
- Supervisor detection correction loop for invalid API payload drafts.
- Approve flow now supports all required mock/live steps currently available, not just rendering.

### 3.3 Partial / deferred / known gaps relative to original Sprint 2 aspirations

- Scheduling path is still mock-agent style (`MockDomainTask` / `MockSupervisorResult`) instead of fully typed production scheduling contracts.
- Google Maps call path exists but is conditional and not default-on; future coverage is still planned.
- Ingest forwarding expects executor `/ingest` internal endpoint, but executor currently exposes `/message`; this requires alignment for fully active ingest-trigger orchestration.
- Dashboard remains function-first and does not yet reflect full late-sprint UX depth from master build spec.

### 3.4 Practical summary

Current MACOS state is no longer Sprint 1 scaffold and is beyond the original Sprint 2 baseline in several orchestration and action-execution areas. The largest maturity gains are:

- detection targeting correctness (name + create/update trigger handling)
- life-graph fidelity with domain-scoped worker context
- structured API payload generation and deterministic approval execution
- stronger supervisor validation/retry/drop controls and verbose execution telemetry

