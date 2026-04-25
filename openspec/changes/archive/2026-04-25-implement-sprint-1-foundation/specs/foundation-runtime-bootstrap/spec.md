## ADDED Requirements

### Requirement: Sprint 1 Repository Foundation
The system SHALL provide the complete Sprint 1 repository structure defined in `MACOS_build_spec_v7_final.md`, including foundational directories and bootstrap files for agents, API, dashboard, and data layers.

#### Scenario: Required foundation paths exist
- **WHEN** Sprint 1 setup tasks are completed
- **THEN** the expected top-level and subsystem scaffold paths exist and are runnable placeholders for subsequent sprint implementation

### Requirement: Sprint 1 Shared Runtime Contracts
The system SHALL implement shared runtime contract files for database access, message models, constants, and LLM wrappers with interfaces matching the Sprint 1 specification.

#### Scenario: Shared runtime modules expose required surfaces
- **WHEN** a developer inspects `agents/shared/{db.py,models.py,constants.py,llm.py}`
- **THEN** each required helper/model/constant/function surface listed in Sprint 1 is present and importable

### Requirement: Deterministic Foundation Seed State
The system SHALL initialize SQLite from `schema.sql` and populate deterministic seed data, including exactly one `org_profile` row and 140 caregiver schedule rows (10 caregivers × 14 days).

#### Scenario: Foundation seed verification passes
- **WHEN** schema initialization and `seed.py` execution complete
- **THEN** `SELECT * FROM org_profile` returns one row and `SELECT COUNT(*) FROM caregiver_schedule` returns `140`

### Requirement: Dashboard Bootstrap Baseline
The system SHALL scaffold Vite + React + Tailwind + React Router with all four top-level routes required by MACOS.

#### Scenario: Route shell boots with four routes
- **WHEN** the dashboard app starts
- **THEN** the router configuration includes Action Feed, Patients, Caregivers, and Org routes

### Requirement: Quickstarter-Style Mock Agent Routing
The scaffold SHALL provide a Fetch quickstarter-style multi-agent topology where executor orchestrates domain routing and each domain returns mock completion responses.

#### Scenario: Executor routes query to domain pipeline
- **WHEN** a query is posted to the executor (REST or chat)
- **THEN** executor classifies domain and sends a `MockDomainTask` to the configured supervisor or scheduling agent

#### Scenario: Supervisor-worker roundtrip completes
- **WHEN** a domain supervisor receives a routed task
- **THEN** the supervisor forwards to its worker, receives `MockWorkerResult`, and returns `MockSupervisorResult` to executor

#### Scenario: Executor endpoint checks pass
- **WHEN** health probes are run against the executor
- **THEN** `/health` reports healthy status and `/message` returns routing metadata containing request id, domain, and routed address
