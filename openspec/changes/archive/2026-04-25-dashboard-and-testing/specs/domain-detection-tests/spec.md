## ADDED Requirements

### Requirement: Health domain deterministic detection tests
The test suite SHALL include tests for each health detection rule check (refill due, missed dose, OpenFDA interaction, OpenFDA recall) using deterministic seed data and asserting expected `ActionDraft` shapes.

#### Scenario: Refill due produces correct draft
- **WHEN** a health detection run is triggered for a patient with a medication due for refill
- **THEN** the detection output contains exactly one `ActionDraft` with `type="medication_refill"`

### Requirement: Appointment domain deterministic detection tests
The test suite SHALL include tests for overdue appointment, transport planning, and visit prep checks using deterministic seed data.

#### Scenario: Overdue appointment produces correct draft
- **WHEN** a detection run is triggered for a patient with a past-due incomplete appointment
- **THEN** the output contains an `ActionDraft` with `type="overdue_appointment"`

### Requirement: Grocery domain deterministic detection tests
The test suite SHALL include tests for delivery staleness, dietary conflict, and supply reorder checks.

#### Scenario: Stale delivery produces reorder draft
- **WHEN** a grocery detection run fires for a patient whose last delivery is more than 7 days ago
- **THEN** the output contains an `ActionDraft` with `type="grocery_reorder"`

### Requirement: Financial domain deterministic detection tests
The test suite SHALL include tests for bill due alert, missed autopay, and spending anomaly checks.

#### Scenario: Bill due produces alert draft
- **WHEN** a financial detection run fires for a patient with a bill due within 5 days
- **THEN** the output contains an `ActionDraft` with `type="bill_due_alert"`
