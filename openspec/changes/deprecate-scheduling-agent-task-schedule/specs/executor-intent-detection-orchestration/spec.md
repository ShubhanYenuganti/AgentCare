## MODIFIED Requirements

### Requirement: Intent classification and routing
The executor SHALL classify inbound requests into intent classes (`question`, `modification`, `detection`) and route to the appropriate downstream handling path. The `scheduling` intent class is removed; time-oriented tasks are handled by domain agents that set a `schedule` field on the resulting action.

#### Scenario: Time-oriented task handled by domain agent
- **WHEN** the executor classifies an inbound request as containing a time-oriented task (e.g., "visit every Thursday 12–4 PM")
- **THEN** the executor routes to the appropriate domain agent, which sets a `schedule` field on the resulting action — no separate scheduling agent is invoked

#### Scenario: Non-scheduling intent routes normally
- **WHEN** the executor classifies an inbound request as `question`, `modification`, or `detection`
- **THEN** routing proceeds as before with no change in behavior

## REMOVED Requirements

### Requirement: Scheduling intent routes to scheduling agent
**Reason**: The scheduling agent is deprecated. Time-oriented intent is now expressed through the `schedule` field on actions, set directly by domain agents. No intermediate agent dispatch is needed.
**Migration**: Remove the `scheduling` branch from executor intent classification. Domain agents (appointment, health, etc.) are responsible for populating `schedule` on time-oriented output actions.
