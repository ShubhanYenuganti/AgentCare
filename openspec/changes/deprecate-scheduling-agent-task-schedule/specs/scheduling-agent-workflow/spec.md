## REMOVED Requirements

### Requirement: Scheduling options generation
**Reason**: The scheduling agent is deprecated. Time-oriented tasks are now handled by domain agents that emit a `schedule` field directly on the action. The agent-to-agent `SchedulingQuery` message flow is no longer needed.
**Migration**: Remove executor routing to the scheduling agent. Domain agents set `schedule` on actions. The `caregiver_schedule` table is queried directly by the new `GET /caregivers/available` endpoint at assignment time.

### Requirement: Chat-selection handler
**Reason**: Caregiver selection is now a direct UI interaction on the Caregivers page, not a chat-based numeric selection flow. The scheduling agent's message-driven selection loop is no longer needed.
**Migration**: Use the new Caregiver assignment panel at `/caregivers?action_id=<id>`, accessed via the "Schedule Task" button on ActionCard.
