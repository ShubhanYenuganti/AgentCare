## ADDED Requirements

### Requirement: Expiration loop dedup tests
The test suite SHALL verify that the executor expiration loop does not send duplicate notifications for the same overdue action across multiple loop runs.

#### Scenario: Dashboard notification deduped
- **WHEN** the expiration loop runs twice for the same overdue action
- **THEN** exactly one `notification_log` entry exists for that action with `channel="dashboard"`

#### Scenario: ASI:One notification deduped
- **WHEN** the expiration loop runs twice for the same overdue action with ASI:One notifications enabled
- **THEN** exactly one `notification_log` entry exists for that action with `channel="asi_one"`

### Requirement: Overdue action marking tests
The test suite SHALL verify that the expiration loop marks actions as overdue when `review_by` is in the past and `completed=0`.

#### Scenario: Action marked overdue
- **WHEN** the expiration loop processes an action with `review_by` in the past and `completed=0`
- **THEN** the action is marked with `is_overdue=true` (or equivalent flag) in the DB
