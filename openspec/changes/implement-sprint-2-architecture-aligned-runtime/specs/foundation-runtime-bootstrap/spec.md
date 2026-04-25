## MODIFIED Requirements

### Requirement: Sprint 1 Shared Runtime Contracts
The system SHALL implement shared runtime contract files for database access, message models, constants, and LLM wrappers with interfaces matching the Sprint 1 specification and Sprint 2 production request/result extensions.

#### Scenario: Shared runtime modules expose required surfaces
- **WHEN** a developer inspects `agents/shared/{db.py,models.py,constants.py,llm.py}`
- **THEN** each required helper/model/constant/function surface listed in Sprint 1 remains present and importable, and Sprint 2 production contracts are available for runtime orchestration

### Requirement: Dashboard Bootstrap Baseline
The system SHALL scaffold Vite + React + Tailwind + React Router with all four top-level routes required by MACOS and wire those routes to live API-backed data states.

#### Scenario: Route shell boots with four routes
- **WHEN** the dashboard app starts
- **THEN** the router configuration includes Action Feed, Patients, Caregivers, and Org routes

#### Scenario: Route views consume live data contracts
- **WHEN** operators navigate to any top-level route
- **THEN** each route MUST fetch and render live API data with explicit loading, empty, and error states

### Requirement: Quickstarter-Style Mock Agent Routing
The scaffold SHALL provide a Fetch quickstarter-style multi-agent topology where executor orchestrates domain routing and each domain supports production request handling while preserving Sprint 1 topology constraints.

#### Scenario: Executor routes query to domain pipeline
- **WHEN** a query is posted to the executor (REST or chat)
- **THEN** executor MUST classify intent/domain and send a typed request to the configured supervisor, scheduling agent, or detection fan-out path

#### Scenario: Supervisor-worker roundtrip completes
- **WHEN** a domain supervisor receives a routed task
- **THEN** the supervisor forwards to its worker, receives typed worker output, and returns typed supervisor output to executor

#### Scenario: Executor endpoint checks pass
- **WHEN** health probes are run against the executor
- **THEN** `/health` reports healthy status and `/message` returns routing metadata containing request id, intent/domain summary, and routed target metadata
