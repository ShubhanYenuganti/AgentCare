## ADDED Requirements

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
