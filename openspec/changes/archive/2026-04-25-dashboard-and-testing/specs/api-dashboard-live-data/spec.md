## ADDED Requirements

### Requirement: Dashboard polling on enriched API responses
The dashboard API client SHALL consume the enriched patient and action list responses added by the backend-domain-and-api-completion change, including `pending_action_count`, `overdue_action_count`, `highest_urgency_level`, `patient_name`, `is_overdue`, and `scheduling_status` fields.

#### Scenario: Enriched patient fields displayed
- **WHEN** the Patient Roster sidebar renders a patient row
- **THEN** it displays `pending_action_count` and `highest_urgency_level` from the enriched API response

#### Scenario: is_overdue field drives banner
- **WHEN** the Action Feed renders a card with `is_overdue=true`
- **THEN** the overdue banner is displayed using the `is_overdue` field from the API response (not a client-side date calculation)
