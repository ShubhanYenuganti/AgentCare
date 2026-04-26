## ADDED Requirements

### Requirement: Intent-First Executor Routing
The executor SHALL classify inbound requests into intent classes (`question`, `modification`, `scheduling`, `detection`) and route to the appropriate downstream handling path.

#### Scenario: Question intent routes to single domain supervisor
- **WHEN** the executor classifies an inbound request as `question` with a resolved domain
- **THEN** it MUST emit a `QuestionRequest` to that domain supervisor and correlate the reply to the originating request id

#### Scenario: Scheduling intent routes to scheduling agent
- **WHEN** the executor classifies an inbound request as `scheduling`
- **THEN** it MUST emit a `SchedulingQuery` to the scheduling agent and return normalized scheduling options

### Requirement: Parallel Detection Fan-Out with Bounded Aggregation
The executor SHALL support detection workflows that fan out to multiple domain supervisors in parallel and aggregate results with timeout bounds.

#### Scenario: Multi-domain detection returns partial success
- **WHEN** at least one domain succeeds and one domain times out or fails
- **THEN** the executor MUST return successful domain results plus per-domain failure metadata instead of failing the entire response

#### Scenario: Detection aggregation deadline expires
- **WHEN** fan-out processing exceeds configured aggregation deadline
- **THEN** the executor MUST finalize the response with completed domains and mark pending domains as timed out

### Requirement: ASI:One Mailbox Boundary Preservation
The executor MUST remain the sole ASI:One mailbox ingress/egress boundary while preserving direct local intra-stack communication for internal hops.

#### Scenario: Chat request receives immediate acknowledgement and correlated final reply
- **WHEN** an ASI:One `ChatMessage` is received through mailbox ingress
- **THEN** the executor MUST send an immediate acknowledgement, run intent orchestration, and send a final correlated `ChatMessage` reply to the original sender address
