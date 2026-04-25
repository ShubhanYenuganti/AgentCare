# Spec: Quickstarter Multi-Agent Scaffold

## Purpose

Defines the requirements for the Fetch quickstarter-style multi-agent scaffold, covering executor-orchestrated routing, domain supervisor-worker pairing, and the mock address strategy supporting both local seed-derived and Agentverse-registered addresses.

## Requirements

### Requirement: Executor-Orchestrated Domain Routing
The scaffold SHALL implement an executor orchestrator that routes incoming messages to domain specialists using deterministic keyword/domain mapping.

#### Scenario: Executor routes incoming request
- **WHEN** the executor receives a chat or REST message
- **THEN** it creates a routed task object with request metadata and dispatches it to the domain supervisor or scheduling agent

### Requirement: Domain Supervisor and Worker Pairing
The scaffold SHALL provide mock supervisor-worker pairs for health, appointment, grocery, and financial domains where supervisor forwards work and worker returns a result.

#### Scenario: Domain worker returns to supervisor
- **WHEN** a domain worker receives a routed task
- **THEN** it returns a domain-specific mock result to its supervisor

#### Scenario: Supervisor returns to executor
- **WHEN** a supervisor receives worker output
- **THEN** it emits a supervisor result message back to executor with request id and domain context

### Requirement: Mock Runtime Address Strategy
The scaffold MUST support local seed-derived addresses and optional override with Agentverse addresses from environment variables.

#### Scenario: Seed fallback works without registration
- **WHEN** no Agentverse address env var is set
- **THEN** agent routing uses deterministic addresses derived from configured seed phrases

#### Scenario: Registered address override
- **WHEN** Agentverse addresses are set in `.env`
- **THEN** routing uses explicit registered addresses rather than seed-derived defaults
