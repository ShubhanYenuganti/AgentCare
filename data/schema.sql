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
  pharmacy_name    TEXT,
  pharmacy_email   TEXT,
  doctor_name      TEXT,
  doctor_email     TEXT,
  preferences_json TEXT,
  life_graph_json  TEXT,
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
  summary         TEXT,
  confirmed       INTEGER DEFAULT 0,
  applied         INTEGER DEFAULT 0,
  created_at      TEXT DEFAULT (datetime('now'))
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

-- Action history
CREATE TABLE IF NOT EXISTS action_history (
  action_id                  TEXT PRIMARY KEY,
  patient_id                 TEXT REFERENCES patients(patient_id),
  domain                     TEXT,
  type                       TEXT,
  description                TEXT,
  draft_content              TEXT,
  draft_version              INTEGER DEFAULT 1,
  modification_in_progress   INTEGER DEFAULT 0,
  urgency_level              TEXT,
  review_by                  TEXT,
  invocation_date            TEXT,
  is_overdue                 INTEGER DEFAULT 0,
  escalation_count           INTEGER DEFAULT 0,
  reviewed                   INTEGER DEFAULT 0,
  completed                  INTEGER DEFAULT 0,
  manual_action_type         TEXT,
  api_payload                TEXT,
  recipient_email            TEXT,
  recipient_type             TEXT,
  email_subject              TEXT,
  scheduling_status          TEXT,
  last_modified_at           TEXT,
  created_at                 TEXT DEFAULT (datetime('now'))
);

-- Action chat history
CREATE TABLE IF NOT EXISTS action_chat (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  action_id     TEXT REFERENCES action_history(action_id),
  role          TEXT,
  content       TEXT,
  intent        TEXT,
  created_at    TEXT DEFAULT (datetime('now'))
);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  type          TEXT,
  action_id     TEXT,
  patient_id    TEXT,
  title         TEXT,
  body          TEXT,
  read          INTEGER DEFAULT 0,
  created_at    TEXT DEFAULT (datetime('now'))
);

-- Expiration notification log
CREATE TABLE IF NOT EXISTS expiration_notifications (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  action_id     TEXT,
  channel       TEXT,
  created_at    TEXT DEFAULT (datetime('now'))
);
