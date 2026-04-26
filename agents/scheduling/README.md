# Scheduling Agent

This agent remains in the repository for compatibility, but scheduling is largely handled by domain actions with `schedule` metadata plus API/UI assignment workflows.

## Status
- Legacy-compatible scheduling helper.
- Not part of the primary detection fan-out domains.
- Current product flow typically uses `/scheduling/*` API routes + caregiver UI for assignment confirmation.

## Component
- `scheduling-agent` (port `8501`)

## Supported message paths
- `MockDomainTask` (legacy mock response path for domain `scheduling`).
- `SchedulingQuery` -> returns `SchedulingOptions`.

## Internal behaviors
- Pulls caregiver availability from mock API.
- Updates action scheduling metadata (`caregiver_options_json`, `scheduling_status`).
- Supports helper functions to:
  - select/book a caregiver (`handle_scheduling_selection`),
  - decline/release assignment (`handle_scheduling_decline`).
- Emits scheduling notifications when state changes.

## Notes
- File header marks this agent as deprecated for primary production scheduling.
- Keep for backward compatibility and integration experiments.

## Running
```bash
python -m agents.scheduling.agent
```
