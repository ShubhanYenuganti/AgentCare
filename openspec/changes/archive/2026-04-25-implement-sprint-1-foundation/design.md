## Context

The MACOS v7 build spec defines a strict sprint order where Sprint 1 creates the baseline required by every subsequent sprint. Sprint 1 spans data schema, shared agent runtime contracts, deterministic seed data, and app scaffolding. It also includes human-executed integration setup (Agentverse registration and environment address mapping) and early ASI:One orchestration preparation to prevent blocked work in scheduling and chat flows later.

Current repository state has only the build spec and OpenSpec scaffolding, so this change must create an implementation plan that is executable end-to-end with clear machine and human responsibilities.

## Goals / Non-Goals

**Goals:**
- Define a concrete Sprint 1 implementation plan that maps directly to the v7 checklist.
- Separate technical build tasks from operator-run tasks while keeping both in one dependency-ordered plan.
- Add explicit readiness gates for external systems (Agentverse and ASI:One) needed for later sprints.
- Make completion verifiable with database and scaffold checks.

**Non-Goals:**
- Implement Sprint 2+ functional behaviors (mock APIs, domain supervisors/workers, scheduling flows, dashboard feature-complete pages).
- Deliver full ASI:One production orchestration logic; Sprint 1 only sets contracts and readiness.
- Resolve non-foundation UX polish or performance optimization.

## Decisions

1. Adopt three capability tracks instead of a single broad capability.
Rationale: Separating `foundation-runtime-bootstrap`, `agent-address-provisioning`, and `asi-one-orchestration-bootstrap` keeps ownership clear and preserves human-intervention gates.
Alternative considered: One combined capability. Rejected because it obscures manual dependencies and makes traceability weaker.

2. Treat Agentverse and ASI:One work as first-class checklist items in `tasks.md`.
Rationale: These are explicit Sprint 1 and cross-sprint dependencies in the source spec and should block completion if skipped.
Alternative considered: Keep them as notes only. Rejected because notes are easy to miss and not trackable by apply workflow.

3. Stage ASI:One orchestration as contract-first in Sprint 1.
Rationale: Define message/address contracts and null-safe behavior now, then implement full query/selection orchestration in Sprint 5-6.
Alternative considered: Defer all ASI:One work to Sprint 5-6. Rejected because late discovery risk is high for external routing assumptions.

4. Keep verification criteria tied to Sprint 1 acceptance checks from the build spec.
Rationale: Sprint checklist already specifies objective checks (`org_profile` row count and caregiver schedule row count), so the plan should anchor to those.
Alternative considered: Define new custom checks. Rejected to avoid drift from source requirements.

5. Reuse Fetch quickstarter orchestration topology for scaffold implementation.
Rationale: The quickstarter provides a proven baseline for orchestrator-to-specialist routing, chat protocol integration, and local seed-based bootstrapping.
Alternative considered: Start with ad hoc MACOS-only stubs. Rejected because it increases integration risk and misses a tested reference architecture.

## Risks / Trade-offs

- [Risk] External service onboarding delays (Agentverse/ASI:One credentials or access) can stall implementation.
  Mitigation: Mark external setup as early tasks with explicit owner and completion proof artifacts.
- [Risk] ASI:One assumptions may change after Sprint 1.
  Mitigation: Document orchestration contracts and keep runtime null-safe when addresses are unset.
- [Risk] Large Sprint 1 surface area can cause incomplete scaffolding.
  Mitigation: Group tasks by subsystem and add concrete done checks per group.
- [Risk] Over-scoping into later sprints.
  Mitigation: Keep this plan scoped to Sprint 1 deliverables and readiness-only tasks for later orchestration.

## Migration Plan

1. Create scaffold and shared modules.
2. Apply SQLite schema and seed dataset.
3. Validate baseline queries and schedule row counts.
4. Complete operator-led Agentverse registration and `.env` address hydration.
5. Complete ASI:One contract and orchestration readiness checklist.
6. Mark Sprint 1 done only after all technical and human gates pass.

Rollback: If a foundation artifact causes instability, revert Sprint 1 changes as a unit and re-run schema/seed from clean DB.

## Open Questions

- Which specific ASI:One environment (sandbox vs production-like) will be used for orchestration validation?
- Who owns long-term address rotation and re-registration on Agentverse?
- Is there a required format for storing external proof artifacts (screenshots/logs) for manual steps?
