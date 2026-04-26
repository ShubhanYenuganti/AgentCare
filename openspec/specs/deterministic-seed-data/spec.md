# Spec: Deterministic Seed Data

## Purpose

Defines the requirements for `data/seed.py` to populate all normalized life-graph tables with exact spec-matching values for all three patients, and to do so idempotently.

## Requirements

### Requirement: seed.py populates all normalized life-graph tables
`data/seed.py` SHALL insert complete patient data for all three spec patients into every normalized domain table, matching the exact values from spec Section 3.3 (medications with adherence_log_json, appointments with last_visit and recommended_frequency_months, grocery with last_delivery and staples, financial bills with autopay flags, financial anomalies for pt_002, emergency contacts, caregiver notes).

#### Scenario: Medications seeded with adherence logs
- **WHEN** seed.py runs and `pt_001` is seeded
- **THEN** the `medications` table contains a row for Lisinopril with `adherence_log_json` set and `refill_due = "2026-04-17"`

#### Scenario: Financial anomaly seeded for pt_002
- **WHEN** seed.py runs and `pt_002` is seeded
- **THEN** the `financial_anomalies` table contains a row for pt_002 with a description referencing the PG&E $340 charge

#### Scenario: Grocery staples seeded for all three patients
- **WHEN** seed.py runs
- **THEN** the `grocery_staples` table contains at least 4 active rows per patient

### Requirement: Seed org profile matches spec values
The seeded `org_profile` row SHALL match the exact field values from spec Section 3.3 ORG_PROFILE, including verbose `health_protocol`, `transport_protocol`, `financial_protocol`, `care_philosophy`, `escalation_chain`, and `escalation_lead`.

#### Scenario: health_protocol includes OpenFDA requirement
- **WHEN** seed.py runs
- **THEN** `get_org_profile()["health_protocol"]` contains the string "OpenFDA"

### Requirement: Seed data supports all detection check thresholds
The seeded data SHALL be structured so that every domain detection check defined in spec Section 6.3–6.9 can fire for at least one patient without code changes:
- pt_001: Lisinopril refill_due is in the past (overdue refill check triggers).
- pt_002: Warfarin+Aspirin co-prescription (OpenFDA interaction check triggers).
- pt_003: Metformin adherence_log has a 4-day gap ending April 19 (missed-dose+worsening check triggers); Medicare Part B due_date is in the past with autopay=True (missed autopay check triggers).
- pt_002: PG&E bill $340 vs prior average $95 (anomaly check triggers).
- pt_001 Cardiology: last_visit "2025-08-10" with recommended_frequency_months=6 (overdue appointment check triggers).

#### Scenario: pt_001 refill is overdue as of seed date
- **WHEN** seed.py runs
- **THEN** `medications` row for med_001 has `refill_due = "2026-04-17"` (8 days before seed date 2026-04-25)

#### Scenario: pt_003 adherence gap is detectable
- **WHEN** seed.py runs
- **THEN** `medications` row for med_004 has `adherence_log_json` whose latest entry is "2026-04-19", leaving a 5-day gap to seed date 2026-04-24

### Requirement: Seed is idempotent and destructive
`seed.py main()` SHALL delete all rows from all tables before inserting, ensuring repeated runs produce identical DB state.

#### Scenario: Running seed twice yields same row counts
- **WHEN** seed.py is run twice in sequence
- **THEN** row counts in all tables are identical after both runs
