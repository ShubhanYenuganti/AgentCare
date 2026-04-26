## ADDED Requirements

### Requirement: POST /actions/{id}/dismiss soft-completes an action without API execution
The endpoint SHALL set `completed=1`, `reviewed=1` on the action and write `completion_date=datetime.utcnow()` and `outcome="dismissed"` to the action record. It SHALL NOT call any external API. It SHALL return the updated action. If the action does not exist, it SHALL return 404.

#### Scenario: dismiss marks action completed
- **WHEN** `POST /actions/act_001/dismiss` is called
- **THEN** the action has `completed=1`, `reviewed=1`, `outcome="dismissed"`, and `completion_date` is set to the current UTC datetime

#### Scenario: dismiss on unknown action returns 404
- **WHEN** `POST /actions/nonexistent/dismiss` is called
- **THEN** the endpoint returns HTTP 404

### Requirement: POST /actions/{id}/approve writes completion metadata
When an action's approval execution succeeds, the endpoint SHALL write `completion_date=datetime.utcnow().isoformat()` and `outcome="approved"` in addition to setting `completed=1` and `reviewed=1`.

#### Scenario: approve writes completion_date and outcome
- **WHEN** `POST /actions/act_001/approve` succeeds (all required steps pass)
- **THEN** the action record has `completion_date` set to a non-null ISO datetime string and `outcome="approved"`
