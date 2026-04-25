## Why

Sprint 1 is the foundation gate for the MACOS build: all later sprints assume a working data layer, shared agent contracts, and runnable service scaffolds. We also need early human-operated setup for Agentverse identities and ASI:One orchestration alignment so external integrations do not block downstream implementation.

## What Changes

- Create the full Sprint 1 repository structure for `agents/`, `api/`, `dashboard/`, and `data/`.
- Implement the complete SQLite schema and shared DB helper surface required by later supervisors, workers, and API routers.
- Implement shared agent primitives: Pydantic models, runtime constants, and Claude wrapper functions including org-context prompt injection.
- Implement deterministic seed data (`org_profile`, 3 patients, 10 caregivers, 14-day schedules, 1 pre-seeded overdue action) and validation checks.
- Scaffold `run_all.py` and dashboard foundation (Vite + React + Tailwind + React Router with 4 routes).
- Adopt the Fetch hackathon quickstarter orchestration pattern for Sprint 1 mock agents: executor-as-orchestrator, domain supervisors/workers, and in-memory stateful routing.
- Add operator-run tasks for Agentverse registration and address propagation into `.env`.
- Add operator-run tasks for ASI:One orchestration bootstrap (address mapping, contract confirmation, and phased handoff readiness for scheduling/chat flows in subsequent sprints).

## Capabilities

### New Capabilities
- `foundation-runtime-bootstrap`: Build and validate the full Sprint 1 technical baseline (schema, shared modules, seed data, runtime scaffolds).
- `quickstarter-multiagent-scaffold`: Establish a quickstarter-derived mock multi-agent architecture to derisk runtime routing before full domain logic implementation.
- `agent-address-provisioning`: Establish human-operated Agentverse registration and environment address hydration as an explicit delivery gate.
- `asi-one-orchestration-bootstrap`: Establish ASI:One integration contracts, null-safe behavior, and forward orchestration readiness checkpoints.

### Modified Capabilities
- None.

## Impact

- Affected code: `data/schema.sql`, `data/seed.py`, `agents/shared/{db.py,models.py,llm.py,constants.py}`, `agents/run_all.py`, dashboard bootstrap files, and environment configuration.
- Affected systems: SQLite local runtime, Agentverse registration workflow, ASI:One routing/orchestration handshake.
- External dependencies: `uagents`, Anthropic key availability, Agentverse account/API key, and operator access to ASI:One environment.
