## MODIFIED Requirements

### Requirement: patients table uses normalized schema
The `patients` table SHALL contain only core identity fields: `patient_id`, `name`, `age`, `address`, `preferences_json`, `active`, `created_at`. It SHALL NOT contain `pharmacy_name`, `pharmacy_email`, `doctor_name`, `doctor_email`, or `life_graph_json` columns. Domain-specific data SHALL live in their respective normalized tables.

#### Scenario: patients table has no life_graph_json column
- **WHEN** `data/schema.sql` is applied to a fresh database
- **THEN** querying `PRAGMA table_info(patients)` returns no column named `life_graph_json`

#### Scenario: write_patient does not persist pharmacy_name
- **WHEN** `db.write_patient({"patient_id": "pt_x", "name": "Test", "pharmacy_name": "CVS"})` is called
- **THEN** the call succeeds without error and no `pharmacy_name` column is written to the patients table
