## ADDED Requirements

### Requirement: Soft-delete on patient data removal
All removal operations on normalized life-graph tables (medications, appointments, grocery, grocery_staples, financial_bills, financial_anomalies, caregiver_notes) SHALL set `active=0` rather than issuing a DELETE, preserving history for audit and anomaly detection.

#### Scenario: Medication removal soft-deleted
- **WHEN** a `patient_update` operation removes a medication entry
- **THEN** the medication row is updated to `active=0` and does not appear in subsequent life graph reads but remains in the DB
