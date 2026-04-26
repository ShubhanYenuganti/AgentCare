# Spec: Normalized Life Graph

## Purpose

Defines the normalized SQLite schema for all life-graph domain entities, the `serialize_life_graph` read path, and the `write_patient` write path that distributes sub-lists into their respective tables.

## Requirements

### Requirement: Normalized life-graph tables exist in schema
The schema SHALL contain separate tables for all life-graph domain entities: `emergency_contacts`, `medications`, `caregiver_notes`, `appointments`, `grocery`, `grocery_staples`, `financial_bills`, `financial_anomalies`. Each table SHALL have a `patient_id` foreign key referencing `patients(patient_id)` and an `active INTEGER DEFAULT 1` column (except `financial_anomalies` and `grocery` which are append-only or single-row).

#### Scenario: Schema tables are present after init
- **WHEN** `data/schema.sql` is applied to a fresh SQLite database
- **THEN** all eight normalized tables exist and are queryable

#### Scenario: Soft-delete via active flag
- **WHEN** a medication, appointment, grocery_staple, emergency_contact, or caregiver_note record is removed via `apply_patient_update`
- **THEN** the row's `active` column is set to `0` and no DELETE is issued

### Requirement: action_history has spec-required columns
The `action_history` table SHALL contain columns `completion_date TEXT`, `assigned_caregiver TEXT`, `caregiver_options_json TEXT`, and `outcome TEXT` as defined in spec Section 3.1.

#### Scenario: write_action persists all spec columns
- **WHEN** `db.write_action()` is called with a dict containing `completion_date`, `assigned_caregiver`, `caregiver_options_json`, and `outcome`
- **THEN** all four values are stored and retrievable via `db.get_action()`

### Requirement: expiration_notifications has notified_at column
The `expiration_notifications` table SHALL contain a `notified_at TEXT` column populated via `datetime('now')` on insert.

#### Scenario: notified_at is set on log
- **WHEN** `db.log_expiration_notification(action_id, channel)` is called
- **THEN** the inserted row has a non-null `notified_at` value

### Requirement: serialize_life_graph builds from normalized tables
`db.serialize_life_graph(patient_id)` SHALL read from all normalized tables (medications, appointments, grocery, grocery_staples, financial_bills, financial_anomalies, emergency_contacts, caregiver_notes) and return a dict with those keys at the top level, using only `active=1` rows.

#### Scenario: serialize returns medication list
- **WHEN** patient `pt_001` has two medications in the `medications` table (one active, one inactive)
- **THEN** `serialize_life_graph("pt_001")["medications"]` returns a list containing only the active medication

#### Scenario: serialize returns grocery staples
- **WHEN** patient has grocery staples seeded in the `grocery_staples` table
- **THEN** `serialize_life_graph(patient_id)["grocery"]["staples"]` is a non-empty list

#### Scenario: serialize returns empty list for missing domain data
- **WHEN** a patient has no rows in `financial_bills`
- **THEN** `serialize_life_graph(patient_id)["financial"]["bills"]` is an empty list (not an error)

### Requirement: write_patient writes to normalized tables
`db.write_patient(data)` SHALL upsert the core `patients` row and write any sub-lists present in `data` (keys: `medications`, `appointments`, `emergency_contacts`, `caregiver_notes`) to their respective normalized tables. Sub-items without a primary key SHALL receive a generated UUID.

#### Scenario: write_patient creates medication rows
- **WHEN** `write_patient` is called with `{"patient_id": "pt_test", "name": "X", "medications": [{"name": "Lisinopril", "dosage": "10mg"}]}`
- **THEN** a row exists in the `medications` table with `patient_id="pt_test"` and `name="Lisinopril"`

### Requirement: get_latest_pending_scheduling_action helper exists
`db.get_latest_pending_scheduling_action()` SHALL return the most recently created `action_history` row where `type='scheduling_task'` and `completed=0`, ordered by `created_at DESC`.

#### Scenario: returns most recent scheduling task
- **WHEN** two scheduling tasks exist with different `created_at` values
- **THEN** the function returns the one with the later `created_at`

#### Scenario: returns None when no pending scheduling tasks
- **WHEN** no scheduling_task rows exist with `completed=0`
- **THEN** the function returns `None`
