## MODIFIED Requirements

### Requirement: Executor-Orchestrated Domain Routing
The scaffold SHALL implement an executor orchestrator that routes incoming messages to domain specialists using explicit intent routing with deterministic fallback mapping.

#### Scenario: Executor routes incoming request
- **WHEN** the executor receives a chat or REST message
- **THEN** it MUST classify intent, create a typed routed request object with request metadata, and dispatch it to the correct supervisor, scheduling agent, or detection fan-out path

#### Scenario: Executor preserves mailbox boundary for ASI:One
- **WHEN** requests originate from ASI:One chat
- **THEN** the executor MUST remain the sole mailbox ingress/egress point and maintain sender-address correlation for final replies

### Requirement: Domain Supervisor and Worker Pairing
The scaffold SHALL provide supervisor-worker pairs for health, appointment, grocery, and financial domains where supervisors orchestrate request lifecycle and workers perform domain enrichment.

#### Scenario: Domain worker returns to supervisor
- **WHEN** a domain worker receives a routed task
- **THEN** it MUST return typed domain output or structured failure to its supervisor

#### Scenario: Supervisor returns to executor
- **WHEN** a supervisor receives worker output
- **THEN** it MUST persist lifecycle updates and emit a supervisor result message back to executor with request id and domain context

### Requirement: Mock Runtime Address Strategy
The scaffold MUST support local seed-derived addresses and optional override with Agentverse addresses from environment variables while preferring local direct routing for in-stack targets.

#### Scenario: Seed fallback works without registration
- **WHEN** no Agentverse address env var is set
- **THEN** agent routing uses deterministic addresses derived from configured seed phrases

#### Scenario: Registered address override
- **WHEN** Agentverse addresses are set in `.env`
- **THEN** routing uses explicit registered addresses rather than seed-derived defaults

#### Scenario: Local-first resolver short-circuits in-stack hops
- **WHEN** executor, supervisors, and workers are running in the same local stack
- **THEN** intra-stack sends MUST resolve to local submit endpoints and avoid mailbox round-trips
