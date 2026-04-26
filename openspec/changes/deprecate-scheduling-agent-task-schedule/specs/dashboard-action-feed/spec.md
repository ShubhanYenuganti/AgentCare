## ADDED Requirements

### Requirement: Schedule Task button on ActionCard
ActionCard SHALL render a **Schedule Task** button as the rightmost of its action buttons, visible when the action is not yet completed and not yet assigned to a caregiver.

#### Scenario: Schedule Task button visible on unassigned action
- **WHEN** an action has `completed = 0` and `assigned_caregiver` is null
- **THEN** the ActionCard shows a "Schedule Task" button as the rightmost button

#### Scenario: Schedule Task button hidden after assignment
- **WHEN** an action has `assigned_caregiver` set to a non-null value
- **THEN** the "Schedule Task" button is not rendered

### Requirement: Schedule Task button navigates to Caregivers with action context
Clicking Schedule Task SHALL navigate the user to `/caregivers?action_id=<action_id>`, passing the action ID as a query parameter so the Caregivers view can open the assignment panel.

#### Scenario: Navigation on click
- **WHEN** user clicks "Schedule Task" on an ActionCard
- **THEN** the browser navigates to `/caregivers?action_id=<id>` without a full page reload

## REMOVED Requirements

### Requirement: scheduling_status display
**Reason**: `scheduling_status` is deprecated in favor of the `schedule` field and explicit caregiver assignment. The field carried implementation-level state that is now expressed through `assigned_caregiver`.
**Migration**: ActionCard renders `assigned_caregiver` to communicate assignment state. No `scheduling_status` display is needed.
