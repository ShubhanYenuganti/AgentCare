## ADDED Requirements

### Requirement: Bill due alert
The financial worker SHALL detect bills due within 5 days that are not marked paid and generate a `type="bill_due_alert"` draft.

#### Scenario: Bill due within window
- **WHEN** a financial bill has `due_date` within 5 days and `paid=0`
- **THEN** the worker generates an `ActionDraft` with `type="bill_due_alert"`, `urgency_level="high"` if within 2 days else `"medium"`

#### Scenario: Bill paid
- **WHEN** a bill has `paid=1`
- **THEN** no bill due alert is generated for that bill

### Requirement: Missed autopay detection
The financial worker SHALL detect bills configured for autopay that did not process by their due date and generate a `type="missed_autopay"` draft.

#### Scenario: Autopay missed
- **WHEN** a bill has `autopay_enabled=1` and `due_date` has passed but `paid=0`
- **THEN** the worker generates an `ActionDraft` with `type="missed_autopay"` and `urgency_level="high"`

### Requirement: Spending anomaly detection
The financial worker SHALL compare the current month's spending against the patient's historical monthly average and generate a `type="spending_anomaly"` draft if spending exceeds 150% of the average.

#### Scenario: Anomaly detected
- **WHEN** current month total spend exceeds 150% of the trailing 3-month average from `financial_anomalies` history
- **THEN** the worker generates an `ActionDraft` with `type="spending_anomaly"`, `urgency_level="medium"`, and the delta amount in `draft_content`

#### Scenario: Spending normal
- **WHEN** current month spend is within 150% of historical average
- **THEN** no anomaly draft is generated
