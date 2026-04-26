-- Organisation profile (single row)
CREATE TABLE IF NOT EXISTS org_profile (
  id                          INTEGER PRIMARY KEY AUTOINCREMENT,
  org_name                    TEXT,
  org_type                    TEXT,
  location                    TEXT,
  patient_count_approx        INTEGER,
  caregiver_count_approx      INTEGER,
  care_philosophy             TEXT,
  decision_making_approach    TEXT,
  continuity_preference       TEXT,
  caregiver_patient_ratio     TEXT,
  visit_frequency_default     INTEGER,
  escalation_chain            TEXT,
  escalation_lead             TEXT,
  health_protocol             TEXT,
  transport_protocol          TEXT,
  financial_protocol          TEXT,
  created_at                  TEXT DEFAULT (datetime('now'))
);

-- Core patient record
CREATE TABLE IF NOT EXISTS patients (
  patient_id       TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  age              INTEGER,
  address          TEXT,
  preferences_json TEXT,
  active           INTEGER DEFAULT 1,
  created_at       TEXT DEFAULT (datetime('now'))
);

-- Patient update audit log
CREATE TABLE IF NOT EXISTS patient_updates (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id      TEXT REFERENCES patients(patient_id),
  caregiver_id    TEXT,
  domain          TEXT,
  operation       TEXT,
  fields_changed  TEXT,
  summary          TEXT,
  proposed_changes TEXT,
  confirmed        INTEGER DEFAULT 0,
  applied          INTEGER DEFAULT 0,
  created_at       TEXT DEFAULT (datetime('now'))
);

-- Caregiver registry
CREATE TABLE IF NOT EXISTS caregivers (
  caregiver_id      TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  email             TEXT,
  phone             TEXT,
  asi_one_address   TEXT,
  role              TEXT DEFAULT 'caregiver'
);

-- Caregiver schedule
CREATE TABLE IF NOT EXISTS caregiver_schedule (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  caregiver_id  TEXT REFERENCES caregivers(caregiver_id),
  date          TEXT,
  start_time    TEXT,
  end_time      TEXT,
  available     INTEGER DEFAULT 1,
  booked        INTEGER DEFAULT 0
);

-- Patient <-> Caregiver assignments
CREATE TABLE IF NOT EXISTS patient_caregivers (
  patient_id    TEXT REFERENCES patients(patient_id),
  caregiver_id  TEXT REFERENCES caregivers(caregiver_id),
  PRIMARY KEY (patient_id, caregiver_id)
);

-- Emergency contacts
CREATE TABLE IF NOT EXISTS emergency_contacts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  TEXT REFERENCES patients(patient_id),
  name        TEXT,
  relation    TEXT,
  phone       TEXT,
  active      INTEGER DEFAULT 1
);

-- Medications
CREATE TABLE IF NOT EXISTS medications (
  med_id              TEXT PRIMARY KEY,
  patient_id          TEXT REFERENCES patients(patient_id),
  name                TEXT,
  dosage              TEXT,
  frequency           TEXT,
  prescriber          TEXT,
  prescriber_email    TEXT,
  pharmacy            TEXT,
  pharmacy_email      TEXT,
  last_refill         TEXT,
  days_supply         INTEGER,
  refill_due          TEXT,
  adherence_log_json  TEXT,
  active              INTEGER DEFAULT 1
);

-- Caregiver notes
CREATE TABLE IF NOT EXISTS caregiver_notes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id    TEXT REFERENCES patients(patient_id),
  caregiver_id  TEXT,
  date          TEXT,
  note          TEXT,
  active        INTEGER DEFAULT 1
);

-- Appointments
CREATE TABLE IF NOT EXISTS appointments (
  appt_id                       TEXT PRIMARY KEY,
  patient_id                    TEXT REFERENCES patients(patient_id),
  provider                      TEXT,
  specialty                     TEXT,
  last_visit                    TEXT,
  next_scheduled                TEXT,
  recommended_frequency_months  INTEGER,
  clinic_address                TEXT,
  phone                         TEXT,
  clinic_email                  TEXT,
  active                        INTEGER DEFAULT 1
);

-- Grocery profile
CREATE TABLE IF NOT EXISTS grocery (
  patient_id                TEXT PRIMARY KEY REFERENCES patients(patient_id),
  dietary_restrictions_json TEXT,
  last_delivery             TEXT
);

CREATE TABLE IF NOT EXISTS grocery_staples (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id      TEXT REFERENCES patients(patient_id),
  item            TEXT,
  frequency_days  INTEGER,
  last_ordered    TEXT,
  active          INTEGER DEFAULT 1
);

-- Financial
CREATE TABLE IF NOT EXISTS financial_bills (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  TEXT REFERENCES patients(patient_id),
  name        TEXT,
  amount      REAL,
  due_date    TEXT,
  autopay     INTEGER DEFAULT 0,
  active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS financial_anomalies (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id   TEXT REFERENCES patients(patient_id),
  description  TEXT,
  detected_at  TEXT
);

-- Central action store
CREATE TABLE IF NOT EXISTS action_history (
  action_id                TEXT PRIMARY KEY,
  patient_id               TEXT REFERENCES patients(patient_id),
  domain                   TEXT,
  type                     TEXT,
  description              TEXT,
  draft_content            TEXT,
  draft_version            INTEGER DEFAULT 1,
  modification_in_progress INTEGER DEFAULT 0,
  urgency_level            TEXT,
  review_by                TEXT,
  invocation_date          TEXT,
  is_overdue               INTEGER DEFAULT 0,
  escalation_count         INTEGER DEFAULT 0,
  reviewed                 INTEGER DEFAULT 0,
  completed                INTEGER DEFAULT 0,
  completion_date          TEXT,
  assigned_caregiver       TEXT,
  scheduling_status        TEXT,
  manual_action_type       TEXT,
  caregiver_options_json   TEXT,
  outcome                  TEXT,
  api_payload              TEXT,
  recipient_email          TEXT,
  recipient_type           TEXT,
  email_subject            TEXT,
  schedule                 TEXT,
  last_modified_at         TEXT,
  created_at               TEXT DEFAULT (datetime('now'))
);

-- Per-action chat thread
CREATE TABLE IF NOT EXISTS action_chat (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  action_id   TEXT REFERENCES action_history(action_id),
  role        TEXT,
  content     TEXT,
  intent      TEXT,
  created_at  TEXT DEFAULT (datetime('now'))
);

-- Global dashboard notifications
CREATE TABLE IF NOT EXISTS notifications (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  type        TEXT,
  action_id   TEXT,
  patient_id  TEXT,
  title       TEXT,
  body        TEXT,
  read        INTEGER DEFAULT 0,
  created_at  TEXT DEFAULT (datetime('now'))
);

-- Expiration notification deduplication
CREATE TABLE IF NOT EXISTS expiration_notifications (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  action_id   TEXT REFERENCES action_history(action_id),
  notified_at TEXT,
  channel     TEXT
);
