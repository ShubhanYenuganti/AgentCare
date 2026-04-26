## 1. Schema (`data/schema.sql`)

- [x] 1.1 Add `emergency_contacts` table (id, patient_id, name, relation, phone, active)
- [x] 1.2 Add `medications` table (med_id PK, patient_id, name, dosage, frequency, prescriber, prescriber_email, pharmacy, pharmacy_email, last_refill, days_supply, refill_due, adherence_log_json, active)
- [x] 1.3 Add `caregiver_notes` table (id, patient_id, caregiver_id, date, note, active)
- [x] 1.4 Add `appointments` table (appt_id PK, patient_id, provider, specialty, last_visit, next_scheduled, recommended_frequency_months, clinic_address, phone, clinic_email, active)
- [x] 1.5 Add `grocery` table (patient_id PK, dietary_restrictions_json, last_delivery) and `grocery_staples` table (id, patient_id, item, frequency_days, last_ordered, active)
- [x] 1.6 Add `financial_bills` table (id, patient_id, name, amount, due_date, autopay, active) and `financial_anomalies` table (id, patient_id, description, detected_at)
- [x] 1.7 Add missing `action_history` columns: `completion_date TEXT`, `assigned_caregiver TEXT`, `caregiver_options_json TEXT`, `outcome TEXT`
- [x] 1.8 Add `notified_at TEXT` column to `expiration_notifications` (spec uses this; current schema only has `created_at`)
- [x] 1.9 Remove denormalized `patients` columns (`pharmacy_name`, `pharmacy_email`, `doctor_name`, `doctor_email`, `life_graph_json`) — data moves to normalized tables

## 2. DB Helpers (`agents/shared/db.py`)

- [x] 2.1 Update `write_patient` to upsert only spec-defined `patients` columns (drop blob columns); fan out sub-lists to normalized tables (`medications`, `appointments`, `emergency_contacts`, `caregiver_notes`, `grocery`, `grocery_staples`, `financial_bills`)
- [x] 2.2 Rewrite `serialize_life_graph` to JOIN across normalized tables (replacing blob read) — return dict with keys: `patient_id`, `name`, `age`, `address`, `preferences`, `emergency_contacts`, `medications`, `caregiver_notes`, `appointments`, `grocery`, `financial`, `assigned_caregivers`
- [x] 2.3 Update `apply_patient_update` to write changes to normalized tables using soft-delete (`active=0`) for removals — no DELETE statements
- [x] 2.4 Update `get_all_patients` and `get_patient` to not reference removed blob columns (`pharmacy_name`, `pharmacy_email`, `doctor_name`, `doctor_email`, `life_graph_json`)
- [x] 2.5 Add `get_latest_pending_scheduling_action(requester_address: str) -> dict` — returns most recent non-completed scheduling_task action for the given requester (used by scheduling agent chat-selection flow)
- [x] 2.6 Update `log_expiration_notification` to write `notified_at=datetime.utcnow()` into the new column
- [x] 2.7 Update `write_action` and `update_action` to handle new `action_history` columns (`completion_date`, `assigned_caregiver`, `caregiver_options_json`, `outcome`)

## 3. Seed Data (`data/seed.py`)

- [x] 3.1 Replace `PATIENTS` list with full spec-defined patient records for pt_001 (Margaret Chen), pt_002 (Robert Harris), pt_003 (Dorothy Kim) — including all nested domain sub-objects matching spec Section 3.3 exactly
- [x] 3.2 Add `_seed_medications` — inserts into `medications` with full adherence_log_json per spec (pt_001: Lisinopril refill 7 days overdue; pt_002: Warfarin+Aspirin interaction pair; pt_003: Metformin with 4-day gap)
- [x] 3.3 Add `_seed_emergency_contacts` — inserts per-patient emergency contacts
- [x] 3.4 Add `_seed_caregiver_notes` — inserts caregiver notes including pt_003 worsening-condition notes from April 22
- [x] 3.5 Add `_seed_appointments` — inserts appointment records (pt_001: Cardiology 8mo overdue; pt_002: Physical Therapy 4mo overdue; pt_003: Endocrinology overdue)
- [x] 3.6 Add `_seed_grocery` — inserts `grocery` row + `grocery_staples` rows per patient
- [x] 3.7 Add `_seed_financial` — inserts `financial_bills` (pt_001: PG&E due in 3 days no autopay; pt_002: PG&E anomaly $340; pt_003: Medicare autopay missed) and `financial_anomalies` for pt_002
- [x] 3.8 Update `_reset_tables` to DELETE from all new tables before re-seeding
- [x] 3.9 Update `_seed_patients` to write only non-blob columns (strip `pharmacy_name`, `pharmacy_email`, `doctor_name`, `doctor_email`, `life_graph_json`)
- [x] 3.10 Update `SEEDED_OVERDUE_ACTION` dict to include new action_history columns (`completion_date=None`, `assigned_caregiver=None`, `caregiver_options_json=None`, `outcome=None`)
- [x] 3.11 Update `main()` to call all new seed functions in dependency order (patients → emergency_contacts → medications → caregiver_notes → appointments → grocery → financial → caregivers → schedule → assignments → overdue_action)

## 4. Executor (`agents/executor/agent.py`)

- [x] 4.1 Fix `run_detection()` org context injection: replace `org_context={}` with `{ k: org.get(k) for k in ORG_CONTEXT_MAP[domain] }` per domain, reading `ORG_CONTEXT_MAP` from `agents/shared/constants.py`
- [x] 4.2 Add `POST /internal/detect` FastAPI route on the executor's REST layer — body: `{ patient_id, trigger, updated_domain }` — calls `run_detection()` via the uagents event loop; return 503 with descriptive error if loop not ready
- [x] 4.3 Add expiration loop `@executor.on_interval(period=900.0)` — fetch overdue actions via `db.get_overdue_actions()`, call `db.mark_action_overdue()`, write dashboard notification via `db.write_notification()` + `db.log_expiration_notification()` with dedup check (`db.has_been_notified()`) for both `dashboard` and `asi_one` channels
- [x] 4.4 In `handle_supervisor_detection_result` (`SupervisorResult` handler), after recording actions, call `db.update_action(action.action_id, {"scheduling_status": "pending_approval"})` for any action where `action.type == "scheduling_task"`
