## ADDED Requirements

### Requirement: ASI:One Contract Baseline
Sprint 1 SHALL define the baseline contract needed for ASI:One-driven interactions, including requester address fields and response pathways used by scheduling and chat workflows.

#### Scenario: ASI:One contract fields are present
- **WHEN** message models and integration notes are reviewed
- **THEN** required requester/recipient address fields for ASI:One interactions are explicitly defined

### Requirement: Null-Safe ASI:One Behavior
The runtime design MUST support null or missing `asi_one_address` values without breaking expiration handling, using dashboard notifications as fallback.

#### Scenario: Missing ASI:One address does not break flow
- **WHEN** overdue escalation runs for a caregiver without `asi_one_address`
- **THEN** ASI:One push is skipped gracefully and dashboard notification remains available

### Requirement: Human-Orchestrated ASI:One Readiness
The implementation plan MUST include human intervention tasks to configure ASI:One orchestration prerequisites and validate routing assumptions for subsequent sprints.

#### Scenario: ASI:One readiness checklist completed
- **WHEN** Sprint 1 manual setup tasks finish
- **THEN** orchestration prerequisites, responsible owner, and verification evidence are documented for Sprint 5-6 execution
