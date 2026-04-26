# Production Domain Runtime

## Purpose

Defines production runtime requirements for domain supervisors and workers, including request lifecycle handling, output normalization, deterministic state transitions, cross-domain modification guards, and Q&A support.

## Requirements

### Requirement: Supervisor Production Request Lifecycle
Each domain supervisor SHALL process production request types (`OnDemandDetectionRequest`, `ModificationRequest`, `QuestionRequest`) and persist lifecycle outcomes through shared data services.

#### Scenario: Detection request persists domain actions
- **WHEN** a supervisor receives an `OnDemandDetectionRequest` for its domain
- **THEN** it MUST dispatch work, persist resulting action drafts/history records, and return a domain-scoped `SupervisorResult` with request correlation metadata

#### Scenario: Modification request updates action lifecycle
- **WHEN** a supervisor receives a `ModificationRequest` for an existing action
- **THEN** it MUST validate transition rules, persist the updated draft/state, and emit a structured modification result including success or rejection reason

### Requirement: Worker Output Normalization
Each domain worker SHALL return normalized outputs that are schema-compatible across executor aggregation and supervisor persistence.

#### Scenario: Worker returns normalized drafts
- **WHEN** worker enrichment completes successfully
- **THEN** the worker MUST return a structured list of `ActionDraft` payloads with domain, urgency, confidence, and evidence fields required by supervisor persistence

#### Scenario: Worker returns structured failure
- **WHEN** enrichment fails due to timeout or provider error
- **THEN** the worker MUST return a typed error payload that allows supervisors to record failure state without corrupting request state

### Requirement: Deterministic Action State Transitions
Action mutation flows SHALL enforce deterministic and auditable state transitions for create, modify, complete, and overdue/escalation updates.

#### Scenario: Invalid transition is rejected
- **WHEN** a request attempts a state transition not permitted by lifecycle rules
- **THEN** the supervisor MUST reject the mutation, preserve prior persisted state, and return a domain-specific validation error

### Requirement: Cross-domain modification guard
Appointment, grocery, and financial domain supervisors SHALL reject `ModificationRequest` messages and return a `ModificationResult` indicating the domain does not support modification, without delegating to a worker.

#### Scenario: Non-health modification rejected
- **WHEN** the appointment, grocery, or financial supervisor receives a `ModificationRequest`
- **THEN** it returns `ModificationResult(revised_draft="not_supported", changes_summary="Modification not supported for this domain")` without calling any worker

### Requirement: Q&A support across all domains
All four domain supervisors SHALL support `QuestionRequest` messages and delegate to a domain worker which optionally calls a live mock API based on the `api_lookup_instruction` field.

#### Scenario: Question answered from snapshot
- **WHEN** a `QuestionRequest` arrives with `api_lookup_instruction=None`
- **THEN** the supervisor delegates to the worker, worker answers from life graph snapshot, supervisor returns `QuestionAnswer`

#### Scenario: Question answered with live API
- **WHEN** a `QuestionRequest` arrives with a non-null `api_lookup_instruction`
- **THEN** the worker calls the specified mock API and incorporates its response into the answer
