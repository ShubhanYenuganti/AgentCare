# MACOS — Full Build Spec v7 (Final)
## Handoff Document for Claude Code

This document is fully self-contained. No prior version of this spec is required.
Everything needed to build the system from scratch is defined here.

---

## 0. HOW TO USE THIS DOCUMENT

Work through sections in order. Each section is a self-contained sprint.
Before starting each sprint, read the full section and implement completely.
Do not scaffold ahead — each sprint depends on the previous being functional.

---

## 1. SYSTEM OVERVIEW

MACOS is a multi-caregiver, multi-patient care operations platform for nonprofit
caregiver organisations. A 3-tier agent hierarchy (Executor → Domain Supervisors →
Domain Workers) monitors all patients across four domains (health, appointment,
grocery, financial), surfaces prioritised actions to a React dashboard, and handles
automated, approval-based, and schedulable manual tasks.

Detection is **event-driven** — triggered immediately when a patient is created or
updated, not on a scheduled loop. The only scheduled loop is a 15-minute expiration
check that escalates overdue actions.

ASI:One (chat interface) handles caregiver queries and scheduling coordination.
The React dashboard has four views: Action Feed, Patient Roster, Caregiver Management,
and Organisation Dashboard.

---

## 2. PROJECT STRUCTURE

```
macos/
├── agents/
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── db.py               # SQLite connection + all read/write helpers
│   │   ├── models.py           # All Pydantic message models
│   │   ├── llm.py              # Claude API wrapper + build_system_prompt()
│   │   └── constants.py
│   ├── executor/
│   │   └── agent.py            # Expiration loop + on-demand detection caller
│   │                           # + intent router + all message handlers
│   ├── health/
│   │   ├── supervisor.py       # Purely message-driven. No interval handler.
│   │   └── worker.py           # Detection + modification + live API Q&A
│   ├── appointment/
│   │   ├── supervisor.py
│   │   └── worker.py
│   ├── grocery/
│   │   ├── supervisor.py
│   │   └── worker.py
│   ├── financial/
│   │   ├── supervisor.py
│   │   └── worker.py
│   ├── scheduling/
│   │   └── agent.py
│   └── run_all.py
│
├── api/
│   ├── main.py
│   ├── routers/
│   │   ├── patients.py         # GET /patients, GET /patients/{id},
│   │   │                       # POST /patients/{id}/update,
│   │   │                       # POST /patients/{id}/update/{uid}/confirm,
│   │   │                       # POST /patients/{id}/update/file,
│   │   │                       # GET /patients/{id}/update-history
│   │   ├── actions.py          # GET /actions, POST approve/dismiss/chat,
│   │   │                       # GET chat-history
│   │   ├── caregivers.py       # GET /caregivers, GET /caregivers/{id},
│   │   │                       # GET /caregivers/{id}/schedule,
│   │   │                       # GET /caregivers/{id}/assignments
│   │   ├── scheduling.py       # GET /scheduling/tasks,
│   │   │                       # POST /scheduling/{id}/assign,
│   │   │                       # POST /scheduling/{id}/confirm,
│   │   │                       # POST /scheduling/{id}/decline
│   │   ├── notifications.py    # GET /notifications,
│   │   │                       # POST /notifications/{id}/read
│   │   ├── ingest.py           # POST /ingest/text, POST /ingest/file
│   │   └── org.py              # GET /org, PUT /org
│   ├── mock_apis/
│   │   ├── cvs.py              # POST /mock/cvs/refill
│   │   ├── cal.py              # POST /mock/cal/book
│   │   ├── instacart.py        # POST /mock/instacart/cart
│   │   ├── amazon.py           # POST /mock/amazon/reorder
│   │   └── caregivers.py       # POST /mock/caregivers/available
│   └── db_bridge.py
│
├── dashboard/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx             # Router: 4 routes + AppShell
│   │   ├── api/
│   │   │   └── client.ts       # All fetch calls organised per view
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppShell.tsx      # Outer shell: TopBar + NavTabs + outlet
│   │   │   │   ├── TopBar.tsx        # Org name, 4 tabs, overdue badge, alert count
│   │   │   │   └── NavTabs.tsx       # 4 tabs: Action Feed | Patients | Caregivers | Org
│   │   │   │
│   │   │   ├── actions/              # ── VIEW 1 ──
│   │   │   │   ├── ActionFeed.tsx
│   │   │   │   ├── ActionCard.tsx    # All 7 states. Modify button: health only.
│   │   │   │   ├── ActionChatPanel.tsx
│   │   │   │   └── DraftModal.tsx
│   │   │   │
│   │   │   ├── patients/             # ── VIEW 2 ──
│   │   │   │   ├── PatientSidebar.tsx
│   │   │   │   ├── PatientCard.tsx
│   │   │   │   ├── PatientDetail.tsx
│   │   │   │   ├── MedicationPanel.tsx
│   │   │   │   ├── AppointmentPanel.tsx
│   │   │   │   ├── GroceryPanel.tsx
│   │   │   │   ├── FinancialPanel.tsx
│   │   │   │   ├── ActionHistoryTable.tsx
│   │   │   │   ├── AddPatientPanel.tsx
│   │   │   │   └── UpdatePatientPanel.tsx
│   │   │   │
│   │   │   ├── caregivers/           # ── VIEW 3 ──
│   │   │   │   ├── CaregiverSidebar.tsx
│   │   │   │   ├── CaregiverCard.tsx
│   │   │   │   ├── CaregiverDetail.tsx
│   │   │   │   ├── ScheduleGrid.tsx
│   │   │   │   ├── AssignmentList.tsx
│   │   │   │   ├── AvailabilityBadge.tsx
│   │   │   │   └── SchedulingPanel.tsx
│   │   │   │
│   │   │   ├── org/                  # ── VIEW 4 ──
│   │   │   │   ├── OrgSummary.tsx
│   │   │   │   ├── ProtocolPanel.tsx
│   │   │   │   ├── CaregiverRoster.tsx
│   │   │   │   └── OrgMetrics.tsx
│   │   │   │
│   │   │   └── shared/
│   │   │       ├── UrgencyBadge.tsx
│   │   │       ├── StatusChip.tsx
│   │   │       ├── Banner.tsx
│   │   │       └── Toast.tsx
│   │   │
│   │   ├── pages/
│   │   │   ├── ActionFeedPage.tsx
│   │   │   ├── PatientRosterPage.tsx
│   │   │   ├── CaregiverPage.tsx
│   │   │   └── OrgDashboardPage.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useActions.ts           # 15s poll
│   │   │   ├── useActionChat.ts        # 3s poll (when panel open)
│   │   │   ├── useNotifications.ts     # 10s poll
│   │   │   ├── usePatients.ts          # 30s poll
│   │   │   ├── usePatient.ts           # 30s poll (when patient selected)
│   │   │   ├── useCaregivers.ts        # 60s poll
│   │   │   ├── useCaregiver.ts         # 30s poll (when caregiver selected)
│   │   │   ├── useCaregiverSchedule.ts # 30s poll (when caregiver selected)
│   │   │   ├── useSchedulingTasks.ts   # 15s poll
│   │   │   └── useOrg.ts               # 300s poll
│   │   │
│   │   └── types/
│   │       └── index.ts
│
├── data/
│   ├── seed.py
│   ├── life_graph.db
│   └── schema.sql
│
├── .env.example
├── requirements.txt
├── package.json
└── README.md
```

---

## 3. DATA LAYER

### 3.1 SQLite Schema (`data/schema.sql`)

```sql
-- Organisation profile (single row — pre-seeded)
CREATE TABLE org_profile (
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
  visit_frequency_default     INTEGER,    -- days between visits
  escalation_chain            TEXT,
  escalation_lead             TEXT,
  health_protocol             TEXT,       -- injected into Health agent prompts
  transport_protocol          TEXT,       -- injected into Appointment agent prompts
  financial_protocol          TEXT,       -- injected into Financial agent prompts
  created_at                  TEXT DEFAULT (datetime('now'))
);

-- Core patient record
CREATE TABLE patients (
  patient_id      TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  age             INTEGER,
  address         TEXT,
  preferences_json TEXT,
  active          INTEGER DEFAULT 1,   -- soft delete: 0 = removed
  created_at      TEXT DEFAULT (datetime('now'))
);

-- Patient update audit log
CREATE TABLE patient_updates (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id      TEXT REFERENCES patients(patient_id),
  caregiver_id    TEXT,
  domain          TEXT,                -- health|appointment|grocery|financial|general
  operation       TEXT,                -- add|update|remove
  fields_changed  TEXT,                -- JSON array of field name strings
  summary         TEXT,                -- LLM-generated plain-language description
  confirmed       INTEGER DEFAULT 0,   -- 1 once caregiver confirms
  applied         INTEGER DEFAULT 0,   -- 1 once written to Life Graph tables
  created_at      TEXT DEFAULT (datetime('now'))
);

-- Caregiver registry
CREATE TABLE caregivers (
  caregiver_id      TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  email             TEXT,
  phone             TEXT,
  asi_one_address   TEXT,              -- placeholder; used for overdue push if set
  role              TEXT DEFAULT 'caregiver'  -- caregiver | admin
);

-- Caregiver schedule (expanded from weekly patterns by seed.py)
CREATE TABLE caregiver_schedule (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  caregiver_id  TEXT REFERENCES caregivers(caregiver_id),
  date          TEXT,         -- ISO date: 2026-04-28
  start_time    TEXT,         -- HH:MM 24h; NULL if unavailable
  end_time      TEXT,         -- HH:MM 24h; NULL if unavailable
  available     INTEGER DEFAULT 1,
  booked        INTEGER DEFAULT 0   -- 1 once a scheduling task is confirmed for this slot
);

-- Patient <-> Caregiver assignments
CREATE TABLE patient_caregivers (
  patient_id    TEXT REFERENCES patients(patient_id),
  caregiver_id  TEXT REFERENCES caregivers(caregiver_id),
  PRIMARY KEY (patient_id, caregiver_id)
);

-- Emergency contacts
CREATE TABLE emergency_contacts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  TEXT REFERENCES patients(patient_id),
  name        TEXT, relation TEXT, phone TEXT,
  active      INTEGER DEFAULT 1
);

-- Medications
CREATE TABLE medications (
  med_id              TEXT PRIMARY KEY,
  patient_id          TEXT REFERENCES patients(patient_id),
  name TEXT, dosage TEXT, frequency TEXT,
  prescriber TEXT, prescriber_email TEXT,
  pharmacy TEXT, pharmacy_email TEXT,
  last_refill TEXT, days_supply INTEGER, refill_due TEXT,
  adherence_log_json  TEXT,   -- JSON array of ISO date strings
  active              INTEGER DEFAULT 1
);

-- Caregiver notes
CREATE TABLE caregiver_notes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id    TEXT REFERENCES patients(patient_id),
  caregiver_id  TEXT,
  date          TEXT,
  note          TEXT,
  active        INTEGER DEFAULT 1
);

-- Appointments
CREATE TABLE appointments (
  appt_id                       TEXT PRIMARY KEY,
  patient_id                    TEXT REFERENCES patients(patient_id),
  provider TEXT, specialty TEXT,
  last_visit TEXT, next_scheduled TEXT,
  recommended_frequency_months  INTEGER,
  clinic_address TEXT, phone TEXT, clinic_email TEXT,
  active                        INTEGER DEFAULT 1
);

-- Grocery profile
CREATE TABLE grocery (
  patient_id                TEXT PRIMARY KEY REFERENCES patients(patient_id),
  dietary_restrictions_json TEXT,
  last_delivery             TEXT
);

CREATE TABLE grocery_staples (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id      TEXT REFERENCES patients(patient_id),
  item TEXT, frequency_days INTEGER, last_ordered TEXT,
  active          INTEGER DEFAULT 1
);

-- Financial
CREATE TABLE financial_bills (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  TEXT REFERENCES patients(patient_id),
  name TEXT, amount REAL, due_date TEXT,
  autopay     INTEGER DEFAULT 0,
  active      INTEGER DEFAULT 1
);

CREATE TABLE financial_anomalies (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id   TEXT REFERENCES patients(patient_id),
  description  TEXT, detected_at TEXT
);

-- Central action store
CREATE TABLE action_history (
  action_id                TEXT PRIMARY KEY,
  patient_id               TEXT REFERENCES patients(patient_id),
  domain                   TEXT NOT NULL,      -- health|appointment|grocery|financial
  type                     TEXT NOT NULL,      -- automated_task|manual_approval|scheduling_task
  description              TEXT,
  draft_content            TEXT,
  draft_version            INTEGER DEFAULT 1,
  last_modified_at         TEXT,
  modification_in_progress INTEGER DEFAULT 0,
  invocation_date          TEXT,
  review_by                TEXT,               -- ISO datetime; also serves as expiry deadline
  urgency_level            TEXT,               -- tier_0|tier_1|tier_2|tier_3
  is_overdue               INTEGER DEFAULT 0,
  escalation_count         INTEGER DEFAULT 0,
  reviewed                 INTEGER DEFAULT 0,
  completed                INTEGER DEFAULT 0,
  completion_date          TEXT,
  assigned_caregiver       TEXT,               -- caregiver_id
  scheduling_status        TEXT,               -- pending_approval|unconfirmed|confirmed|unresolved
  manual_action_type       TEXT,               -- transport|grocery_delivery|supply_reorder
  caregiver_options_json   TEXT,
  outcome                  TEXT,
  created_at               TEXT DEFAULT (datetime('now'))
);

-- Per-action chat thread (Q&A + modification requests)
CREATE TABLE action_chat (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  action_id   TEXT REFERENCES action_history(action_id),
  role        TEXT NOT NULL,    -- user | agent
  intent      TEXT,             -- question | modification | null
  content     TEXT NOT NULL,
  created_at  TEXT DEFAULT (datetime('now'))
);

-- Global dashboard notifications
CREATE TABLE notifications (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  type        TEXT NOT NULL,   -- modification_complete|overdue|new_action|scheduling_update
  action_id   TEXT REFERENCES action_history(action_id),
  patient_id  TEXT,
  title       TEXT,
  body        TEXT,
  read        INTEGER DEFAULT 0,
  created_at  TEXT DEFAULT (datetime('now'))
);

-- Expiration notification deduplication
CREATE TABLE expiration_notifications (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  action_id   TEXT REFERENCES action_history(action_id),
  notified_at TEXT,
  channel     TEXT    -- dashboard | asi_one
);
```

### 3.2 `agents/shared/db.py` — complete function list

```python
# ── Org helpers ──────────────────────────────────────────────────────────────
def get_org_profile() -> dict
    # Returns single org_profile row as dict. Returns {} if not seeded.
def update_org_profile(updates: dict)
    # Partial update to org_profile row.

# ── Patient helpers ──────────────────────────────────────────────────────────
def get_all_patients() -> list[dict]
    # WHERE active=1 only. Returns list of PatientSummary dicts.
def get_patient(patient_id: str) -> dict
    # Returns single patient row.
def write_patient(data: dict) -> str
    # Upsert from Life Graph dict. Returns patient_id.
def serialize_life_graph(patient_id: str) -> dict
    # Joins all tables for patient. active=1 rows only.
    # Returns full Life Graph JSON dict.

# ── Patient update helpers ───────────────────────────────────────────────────
def write_patient_update(update: dict) -> int
    # Inserts into patient_updates. Returns id.
def get_patient_update(update_id: int) -> dict
    # Returns single patient_updates row.
def confirm_patient_update(update_id: int)
    # Sets confirmed=1.
def apply_patient_update(update_id: int, changes: dict)
    # Writes changes to relevant Life Graph tables. Sets applied=1.
    # NEVER issues DELETE — sets active=0 for removals.
def get_patient_update_history(patient_id: str) -> list[dict]
    # Returns all patient_updates rows for patient, newest first.

# ── Action helpers ───────────────────────────────────────────────────────────
def write_action(action: dict) -> str
    # Upserts action_history row. Returns action_id.
def get_action(action_id: str) -> dict
    # Returns single action_history row as dict.
def get_pending_actions(patient_id: str = None, domain: str = None,
                        type: str = None) -> list[dict]
    # Returns non-completed actions, optionally filtered.
def get_overdue_actions() -> list[dict]
    # WHERE review_by < now AND completed=0 AND is_overdue=0
def mark_action_overdue(action_id: str)
    # Sets is_overdue=1, urgency_level='tier_0', escalation_count += 1
def update_action(action_id: str, updates: dict)
    # Partial update to action_history row.
def replace_draft(action_id: str, new_draft: str)
    # Sets draft_content=new_draft, draft_version+=1,
    # last_modified_at=now(), modification_in_progress=0
def set_modification_in_progress(action_id: str, in_progress: bool)
    # Sets modification_in_progress=1 or 0.
def get_action_rankings() -> list[dict]
    # Returns all pending actions sorted by:
    # is_overdue DESC, score DESC, created_at ASC
    # score = URGENCY_SCORES[urgency_level] + DOMAIN_PRIORITY[domain]
    #       + OVERDUE_SCORE_BOOST if is_overdue=1

# ── Chat helpers ─────────────────────────────────────────────────────────────
def write_chat_message(action_id: str, role: str, content: str,
                       intent: str = None) -> int
    # Inserts row into action_chat. Returns row id.
def get_chat_history(action_id: str) -> list[dict]
    # Returns all messages for action ordered by created_at ASC.
def replace_last_agent_message(action_id: str, new_content: str)
    # UPDATE action_chat SET content=new_content
    # WHERE action_id=? AND role='agent' ORDER BY id DESC LIMIT 1

# ── Notification helpers ─────────────────────────────────────────────────────
def write_notification(type: str, action_id: str, patient_id: str,
                       title: str, body: str) -> int
    # Inserts into notifications. Returns id.
def get_unread_notifications() -> list[dict]
    # WHERE read=0, ORDER BY created_at DESC
def mark_notification_read(notification_id: int)
    # Sets read=1.
def log_expiration_notification(action_id: str, channel: str)
    # Inserts into expiration_notifications.
def has_been_notified(action_id: str, channel: str) -> bool
    # Returns True if row exists in expiration_notifications for this action+channel.

# ── Caregiver helpers ────────────────────────────────────────────────────────
def get_all_caregivers() -> list[dict]
    # Returns all caregivers with today's availability status injected.
def get_caregiver(caregiver_id: str) -> dict
    # Returns single caregiver with availability + assignments + scheduling tasks.
def get_caregiver_schedule(caregiver_id: str,
                           start_date: str, end_date: str) -> list[dict]
    # Returns all caregiver_schedule rows for caregiver in date range.
def get_caregiver_assignments(caregiver_id: str) -> list[dict]
    # Returns all patients assigned to this caregiver + pending action counts.
def get_caregiver_available_slots(date: str,
                                  duration_hours: float = 2.0) -> list[dict]
    # Returns caregivers with available=1, booked=0 on given date.
    # Sorted: assigned_to_patient caregivers first, then by start_time.
def book_caregiver_slot(caregiver_id: str, date: str)
    # Sets booked=1 for that caregiver's slot on that date.
def free_caregiver_slot(caregiver_id: str, date: str)
    # Sets booked=0 — called on scheduling decline or dismiss.
def get_scheduling_tasks() -> list[dict]
    # All pending actions WHERE type='scheduling_task'.
    # Sorted by is_overdue DESC, urgency_level score DESC, created_at ASC.
```

### 3.3 `data/seed.py` — complete seed content

#### Org Profile

```python
ORG_PROFILE = {
    "org_name": "Sunrise Care Org",
    "org_type": "nonprofit home care",
    "location": "San Francisco, CA",
    "patient_count_approx": 12,
    "caregiver_count_approx": 10,
    "care_philosophy": (
        "Person-centred care prioritising patient autonomy and dignity. "
        "Caregivers act as advocates, not just task executors."
    ),
    "decision_making_approach": (
        "Conservative — escalate early, prefer over-communication to under-communication."
    ),
    "continuity_preference": "Assign same caregivers to patients where possible.",
    "caregiver_patient_ratio": "1:3 maximum",
    "visit_frequency_default": 7,
    "escalation_chain": "Caregiver → Org Admin → Patient Emergency Contact",
    "escalation_lead": "Admin — Dr. Priya Nair",
    "health_protocol": (
        "Flag any missed medication dose streak >= 3 days. "
        "Always cc prescriber on refill requests. "
        "OpenFDA interaction checks mandatory for polypharmacy patients (3+ meds)."
    ),
    "transport_protocol": (
        "Family transport preferred if listed. "
        "Caregiver transport requires 48h advance notice minimum. "
        "Always confirm departure time with patient the day before."
    ),
    "financial_protocol": (
        "No payment actions without caregiver sign-off. "
        "Flag any bill variance >20% from prior period. "
        "Medicare/Medi-Cal bills reviewed by admin before action."
    ),
}
```

#### Patients

```python
PATIENTS = [
    {
        "patient_id": "pt_001",
        "name": "Margaret Chen",
        "age": 74,
        "address": "123 Sunset Blvd, San Francisco, CA 94122",
        "preferences": {
            "appointment_times": ["morning"],
            "transport_preference": "family_first"
        },
        "emergency_contacts": [
            { "name": "Linda Chen", "relation": "daughter", "phone": "+1-555-0192" }
        ],
        "medications": [
            {
                "med_id": "med_001",
                "name": "Lisinopril",
                "dosage": "10mg",
                "frequency": "once daily",
                "prescriber": "Dr. Anita Patel",
                "prescriber_email": "dr.patel@ucsf-cardiology.com",
                "pharmacy": "CVS Mission St",
                "pharmacy_email": "cvs.missionst@cvs.com",
                "last_refill": "2026-03-18",
                "days_supply": 30,
                "refill_due": "2026-04-17",   # 7 days overdue as of seed date
                "adherence_log": [
                    "2026-04-23", "2026-04-22", "2026-04-21",
                    "2026-04-20", "2026-04-19"
                ]
            }
        ],
        "caregiver_notes": [
            {
                "caregiver_id": "cg_001",
                "date": "2026-04-21",
                "note": "Margaret seemed tired today, resting most of the afternoon."
            }
        ],
        "appointments": [
            {
                "appt_id": "appt_001",
                "provider": "Dr. Anita Patel",
                "specialty": "Cardiology",
                "last_visit": "2025-08-10",   # 8 months overdue
                "next_scheduled": None,
                "recommended_frequency_months": 6,
                "clinic_address": "400 Parnassus Ave, SF CA 94143",
                "phone": "+1-555-0144",
                "clinic_email": "cardiology@ucsf.edu"
            }
        ],
        "grocery": {
            "dietary_restrictions": ["low sodium", "diabetic-friendly"],
            "last_delivery": "2026-04-12",    # 12 days ago
            "staples": [
                { "item": "spinach",        "frequency_days": 7,  "last_ordered": "2026-04-12" },
                { "item": "chicken breast", "frequency_days": 7,  "last_ordered": "2026-04-12" },
                { "item": "brown rice",     "frequency_days": 14, "last_ordered": "2026-04-12" },
                { "item": "greek yogurt",   "frequency_days": 7,  "last_ordered": "2026-04-12" },
            ]
        },
        "financial": {
            "bills": [
                {
                    "name": "PG&E",
                    "amount": 94.00,
                    "due_date": "2026-04-27",   # 3 days away, autopay off
                    "autopay": False
                },
                {
                    "name": "Medicare Part B",
                    "amount": 174.70,
                    "due_date": "2026-05-01",
                    "autopay": True
                }
            ]
        },
        "assigned_caregivers": ["cg_001", "cg_002"]
    },

    {
        "patient_id": "pt_002",
        "name": "Robert Harris",
        "age": 81,
        "address": "88 Ocean Ave, San Francisco, CA 94112",
        "preferences": {
            "appointment_times": ["morning"],
            "transport_preference": "caregiver"
        },
        "emergency_contacts": [
            { "name": "Tom Harris", "relation": "son", "phone": "+1-555-0234" }
        ],
        "medications": [
            {
                "med_id": "med_002",
                "name": "Warfarin",
                "dosage": "5mg",
                "frequency": "once daily",
                "prescriber": "Dr. James Okonkwo",
                "prescriber_email": "dr.okonkwo@sfgeneral.org",
                "pharmacy": "Walgreens Excelsior",
                "pharmacy_email": "walgreens.excelsior@walgreens.com",
                "last_refill": "2026-04-01",
                "days_supply": 30,
                "refill_due": "2026-05-01",
                "adherence_log": [
                    "2026-04-23", "2026-04-22", "2026-04-21",
                    "2026-04-20", "2026-04-19", "2026-04-18"
                ]
            },
            {
                "med_id": "med_003",
                "name": "Aspirin",
                "dosage": "81mg",
                "frequency": "once daily",
                "prescriber": "Dr. James Okonkwo",
                "prescriber_email": "dr.okonkwo@sfgeneral.org",
                "pharmacy": "Walgreens Excelsior",
                "pharmacy_email": "walgreens.excelsior@walgreens.com",
                "last_refill": "2026-04-01",
                "days_supply": 30,
                "refill_due": "2026-05-01",
                "adherence_log": [
                    "2026-04-23", "2026-04-22", "2026-04-21",
                    "2026-04-20", "2026-04-19", "2026-04-18"
                ]
            }
            # Warfarin + Aspirin co-prescription → OpenFDA interaction flag fires
        ],
        "caregiver_notes": [
            {
                "caregiver_id": "cg_002",
                "date": "2026-04-22",
                "note": "Robert in good spirits, walked to the garden independently."
            }
        ],
        "appointments": [
            {
                "appt_id": "appt_002",
                "provider": "Dr. Maya Torres",
                "specialty": "Physical Therapy",
                "last_visit": "2026-01-03",   # 4 months overdue
                "next_scheduled": None,
                "recommended_frequency_months": 3,
                "clinic_address": "1001 Potrero Ave, SF CA 94110",
                "phone": "+1-555-0311",
                "clinic_email": "physio@sfgeneral.org"
            }
        ],
        "grocery": {
            "dietary_restrictions": ["low fat", "heart healthy"],
            "last_delivery": "2026-04-20",
            "staples": [
                { "item": "oatmeal",     "frequency_days": 7, "last_ordered": "2026-04-20" },
                { "item": "salmon",      "frequency_days": 7, "last_ordered": "2026-04-20" },
                { "item": "blueberries", "frequency_days": 7, "last_ordered": "2026-04-20" },
                { "item": "whole milk",  "frequency_days": 7, "last_ordered": "2026-04-20" },
            ]
        },
        "financial": {
            "bills": [
                {
                    "name": "Pacific Gas & Electric",
                    "amount": 340.00,   # anomaly — prior average $95 (258% above)
                    "due_date": "2026-04-30",
                    "autopay": False
                },
                {
                    "name": "Medicare Part B",
                    "amount": 174.70,
                    "due_date": "2026-05-01",
                    "autopay": True
                }
            ],
            "anomalies": [
                {
                    "description": "PG&E charge $340 vs prior average $95 — 258% above baseline",
                    "detected_at": "2026-04-23"
                }
            ]
        },
        "assigned_caregivers": ["cg_001", "cg_002"]
    },

    {
        "patient_id": "pt_003",
        "name": "Dorothy Kim",
        "age": 68,
        "address": "45 Noriega St, San Francisco, CA 94122",
        "preferences": {
            "appointment_times": ["afternoon"],
            "transport_preference": "family_first"
        },
        "emergency_contacts": [
            { "name": "Grace Kim", "relation": "niece", "phone": "+1-555-0388" }
        ],
        "medications": [
            {
                "med_id": "med_004",
                "name": "Metformin",
                "dosage": "500mg",
                "frequency": "twice daily",
                "prescriber": "Dr. Carlos Reyes",
                "prescriber_email": "dr.reyes@sfdiabetesclinic.com",
                "pharmacy": "Rite Aid Taraval",
                "pharmacy_email": "riteaid.taraval@riteaid.com",
                "last_refill": "2026-04-01",
                "days_supply": 30,
                "refill_due": "2026-05-01",
                "adherence_log": [
                    # 4-day consecutive gap — last dose April 19th
                    "2026-04-19", "2026-04-18", "2026-04-17",
                    "2026-04-16", "2026-04-15"
                ]
            }
        ],
        "caregiver_notes": [
            {
                "caregiver_id": "cg_001",
                "date": "2026-04-22",
                "note": "Dorothy reported increased fatigue and dizziness. She declined lunch and spent most of the day in bed."
            },
            {
                "caregiver_id": "cg_002",
                "date": "2026-04-21",
                "note": "Dorothy seemed withdrawn today, less talkative than usual."
            }
        ],
        "appointments": [
            {
                "appt_id": "appt_003",
                "provider": "Dr. Carlos Reyes",
                "specialty": "Endocrinology",
                "last_visit": "2026-01-15",
                "next_scheduled": None,
                "recommended_frequency_months": 3,
                "clinic_address": "2340 Sutter St, SF CA 94115",
                "phone": "+1-555-0421",
                "clinic_email": "appointments@sfdiabetesclinic.com"
            }
        ],
        "grocery": {
            "dietary_restrictions": ["diabetic-friendly", "low sugar"],
            "last_delivery": "2026-04-18",
            "staples": [
                { "item": "leafy greens",   "frequency_days": 7,  "last_ordered": "2026-04-18" },
                { "item": "eggs",           "frequency_days": 7,  "last_ordered": "2026-04-18" },
                { "item": "almonds",        "frequency_days": 14, "last_ordered": "2026-04-18" },
                { "item": "cottage cheese", "frequency_days": 7,  "last_ordered": "2026-04-18" },
            ]
        },
        "financial": {
            "bills": [
                {
                    "name": "Medicare Part B",
                    "amount": 174.70,
                    "due_date": "2026-04-01",   # past due — autopay missed
                    "autopay": True
                }
            ]
        },
        "assigned_caregivers": ["cg_001", "cg_002"]
    }
]
```

#### Caregivers

```python
CAREGIVERS = [
    {
        "caregiver_id": "cg_001", "name": "Sarah Okafor",
        "email": "sarah@sunrisecare.org", "phone": "+1-555-1001",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Mon","Tue","Wed","Thu","Fri"],
                               "start": "08:00", "end": "16:00" }
    },
    {
        "caregiver_id": "cg_002", "name": "James Reyes",
        "email": "james@sunrisecare.org", "phone": "+1-555-1002",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Mon","Wed","Fri"],
                               "start": "09:00", "end": "17:00" }
    },
    {
        "caregiver_id": "cg_003", "name": "Linda Park",
        "email": "linda@sunrisecare.org", "phone": "+1-555-1003",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Tue","Thu","Sat"],
                               "start": "07:00", "end": "15:00" }
    },
    {
        "caregiver_id": "cg_004", "name": "Marcus Webb",
        "email": "marcus@sunrisecare.org", "phone": "+1-555-1004",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Mon","Tue","Thu","Fri"],
                               "start": "10:00", "end": "18:00" }
    },
    {
        "caregiver_id": "cg_005", "name": "Priya Nair",
        "email": "priya@sunrisecare.org", "phone": "+1-555-1005",
        "asi_one_address": None, "role": "admin",
        "schedule_pattern": { "days": ["Wed","Thu","Fri","Sat"],
                               "start": "08:00", "end": "14:00" }
    },
    {
        "caregiver_id": "cg_006", "name": "Tom Callahan",
        "email": "tom@sunrisecare.org", "phone": "+1-555-1006",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Mon","Tue","Wed"],
                               "start": "12:00", "end": "20:00" }
    },
    {
        "caregiver_id": "cg_007", "name": "Aisha Diallo",
        "email": "aisha@sunrisecare.org", "phone": "+1-555-1007",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Thu","Fri","Sat","Sun"],
                               "start": "08:00", "end": "16:00" }
    },
    {
        "caregiver_id": "cg_008", "name": "Kevin Huang",
        "email": "kevin@sunrisecare.org", "phone": "+1-555-1008",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Mon","Wed","Fri","Sun"],
                               "start": "09:00", "end": "17:00" }
    },
    {
        "caregiver_id": "cg_009", "name": "Rosa Medina",
        "email": "rosa@sunrisecare.org", "phone": "+1-555-1009",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Tue","Wed","Thu"],
                               "start": "07:00", "end": "15:00" }
    },
    {
        "caregiver_id": "cg_010", "name": "Daniel Frost",
        "email": "daniel@sunrisecare.org", "phone": "+1-555-1010",
        "asi_one_address": None, "role": "caregiver",
        "schedule_pattern": { "days": ["Mon","Tue","Wed","Thu","Fri"],
                               "start": "14:00", "end": "22:00" }
    },
]
```

**Note on `asi_one_address`:** Used by the expiration loop to push overdue
notifications to caregivers via ASI:One. For the demo, all values are `None`.
The expiration loop gracefully skips the ASI:One push when this field is null
and relies on dashboard notifications instead.

#### Schedule Expansion

```python
from datetime import date, timedelta

DAY_MAP = { "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3,
            "Fri": 4, "Sat": 5, "Sun": 6 }

def expand_schedule(caregiver: dict, start_date: date, days: int = 14) -> list[dict]:
    pattern = caregiver["schedule_pattern"]
    working_days = set(DAY_MAP[d] for d in pattern["days"])
    rows = []
    for i in range(days):
        target = start_date + timedelta(days=i)
        working = target.weekday() in working_days
        rows.append({
            "caregiver_id": caregiver["caregiver_id"],
            "date": target.isoformat(),
            "start_time": pattern["start"] if working else None,
            "end_time":   pattern["end"]   if working else None,
            "available":  1 if working else 0,
            "booked": 0
        })
    return rows

# In seed.py main():
SEED_DATE = date(2026, 4, 24)
for cg in CAREGIVERS:
    for row in expand_schedule(cg, SEED_DATE, days=14):
        # INSERT INTO caregiver_schedule ...
```

#### Patient → Caregiver Assignments

```python
# cg_001 and cg_002 are primary caregivers, assigned to all 3 patients.
# All other caregivers are org-wide pool for scheduling tasks only.
PATIENT_CAREGIVER_ASSIGNMENTS = [
    ("pt_001", "cg_001"), ("pt_001", "cg_002"),
    ("pt_002", "cg_001"), ("pt_002", "cg_002"),
    ("pt_003", "cg_001"), ("pt_003", "cg_002"),
]
```

#### Pre-seeded Overdue Action

```python
# Pre-seed one overdue action so the expiration state is visible immediately
# on demo load, without waiting for the 15-minute expiration loop to fire.
SEEDED_OVERDUE_ACTION = {
    "action_id": "act_seed_overdue_001",
    "patient_id": "pt_003",           # Dorothy Kim
    "domain": "health",
    "type": "manual_approval",
    "description": "Metformin missed 4 days — condition worsening escalation",
    "draft_content": (
        "Dear Dr. Reyes,\n\nI am writing to escalate a concern regarding "
        "Dorothy Kim (68). She has missed her Metformin 500mg for 4 consecutive "
        "days. Caregiver notes from April 22nd document increased fatigue and "
        "dizziness. We recommend urgent review and guidance on next steps.\n\n"
        "Regards,\nSunrise Care Org"
    ),
    "urgency_level": "tier_0",
    "is_overdue": 1,
    "review_by": "2026-04-23T09:00:00Z",   # past → already overdue
    "invocation_date": "2026-04-23T07:00:00Z",
    "escalation_count": 1,
    "reviewed": 0,
    "completed": 0,
}
```

---

## 4. SHARED AGENT UTILITIES

### 4.1 `agents/shared/models.py` — complete model definitions

```python
from uagents import Model

# ── Detection pipeline ────────────────────────────────────────────────────────

class OnDemandDetectionRequest(Model):
    """Executor → Domain Supervisor. Fired on patient_create or patient_update."""
    patient_id: str
    trigger: str                # 'patient_create' | 'patient_update'
    pass_id: str                # UUID for this detection pass
    updated_domain: str | None  # Which domain changed (patient_update only).
                                # Supervisors outside this domain may deprioritise.
    org_context: dict           # Relevant org_profile fields for this supervisor.

class ActionDraft(Model):
    """Domain Worker → Domain Supervisor. One draft action."""
    action_id: str
    patient_id: str
    domain: str
    type: str                   # automated_task | manual_approval | scheduling_task
    description: str
    draft_content: str | None
    urgency_level: str          # tier_0 | tier_1 | tier_2 | tier_3
    review_by: str              # ISO datetime — also serves as expiry deadline
    manual_action_type: str | None  # transport | grocery_delivery | supply_reorder
    api_payload: dict | None    # Pre-built payload for mock API calls
    recipient_email: str | None
    recipient_type: str | None  # pharmacy | prescriber | clinic

class WorkerResult(Model):
    """Domain Worker → Domain Supervisor. All drafts from one detection pass."""
    pass_id: str
    patient_id: str
    domain: str
    drafts: list[ActionDraft]

class SupervisorResult(Model):
    """Domain Supervisor → Executor. Risk-scored, framed, DB-written actions."""
    pass_id: str
    patient_id: str
    domain: str
    actions: list[ActionDraft]

# ── Scheduling pipeline ───────────────────────────────────────────────────────

class SchedulingQuery(Model):
    """Executor → Scheduling Agent. When caregiver queries via ASI:One."""
    action_id: str
    patient_id: str
    manual_action_type: str
    description: str
    required_date: str | None
    requester_address: str      # ASI:One address to reply to

class SchedulingOptions(Model):
    """Scheduling Agent → Executor / ASI:One. Available caregiver list."""
    action_id: str
    options: list[dict]         # [{ caregiver_id, name, date, start_time, end_time }]

# ── Modification pipeline (health domain only) ────────────────────────────────

class ModificationRequest(Model):
    """Executor → Health Supervisor."""
    action_id: str
    patient_id: str
    domain: str
    action_type: str            # automated_task | manual_approval
    current_draft: str
    modification_instruction: str
    life_graph_snapshot: str    # JSON string of patient Life Graph

class ModificationTask(Model):
    """Health Supervisor → Health Worker (only if live API data needed)."""
    action_id: str
    patient_id: str
    domain: str
    action_type: str
    current_draft: str
    modification_instruction: str
    requires_live_api: bool
    api_context: str | None     # Which API and why

class ModificationDraft(Model):
    """Health Worker → Health Supervisor."""
    action_id: str
    revised_draft: str
    changes_summary: str

class ModificationResult(Model):
    """Health Supervisor → Executor."""
    action_id: str
    patient_id: str
    revised_draft: str
    changes_summary: str        # Shown in global toast notification

# ── Q&A pipeline (all domains) ───────────────────────────────────────────────

class QuestionRequest(Model):
    """Executor → Domain Supervisor."""
    action_id: str
    patient_id: str
    domain: str
    action_type: str
    question: str
    current_draft: str | None
    life_graph_snapshot: str

class QuestionTask(Model):
    """Domain Supervisor → Domain Worker (only if live API lookup needed)."""
    action_id: str
    patient_id: str
    domain: str
    question: str
    api_lookup_instruction: str

class QuestionApiResult(Model):
    """Domain Worker → Domain Supervisor."""
    action_id: str
    api_data: str

class QuestionAnswer(Model):
    """Domain Supervisor → Executor."""
    action_id: str
    answer: str
    requires_action: bool
    suggested_action: str | None

# ── Expiration ────────────────────────────────────────────────────────────────

class ExpirationEscalation(Model):
    action_id: str
    patient_id: str
    description: str
    urgency_level: str
    assigned_caregiver: str | None
    action_type: str
```

### 4.2 `agents/shared/llm.py`

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

def call_claude(system: str, user: str, max_tokens: int = 1000) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return response.content[0].text

def call_claude_json(system: str, user: str, max_tokens: int = 1000) -> dict:
    text = call_claude(system, user, max_tokens)
    import json
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)

def call_claude_vision(b64_image: str, media_type: str, prompt: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                    "media_type": media_type, "data": b64_image}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    text = response.content[0].text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    import json
    return json.loads(text)

def build_system_prompt(base_prompt: str, org_context: dict, domain: str) -> str:
    """
    Prepends org context to any agent system prompt.
    Must be called for every LLM invocation in Supervisors and Workers.
    """
    org_section = f"""Organisation context:
- Care philosophy: {org_context.get('care_philosophy', 'Not specified')}
- {domain.capitalize()} protocol: {org_context.get(f'{domain}_protocol', 'Standard protocol')}
- Escalation chain: {org_context.get('escalation_chain', 'Caregiver → Admin')}
- Escalation lead: {org_context.get('escalation_lead', 'Admin')}

Apply this context when drafting emails, assessing risk, and framing actions.
"""
    return org_section + "\n" + base_prompt
```

### 4.3 `agents/shared/constants.py`

```python
# review_by windows in hours (= expiry deadline)
REVIEW_BY_HOURS = {
    "tier_0": 2,
    "tier_1": 24,
    "tier_2": 48,
    "tier_3": 168,  # 7 days
}

# Urgency score for global action ranking
URGENCY_SCORES = {
    "tier_0": 100,
    "tier_1": 75,
    "tier_2": 50,
    "tier_3": 25,
}

# Overdue actions boosted above any non-overdue action
OVERDUE_SCORE_BOOST = 200

# Domain priority bonus added to urgency score
DOMAIN_PRIORITY = {
    "health": 10,
    "appointment": 7,
    "financial": 5,
    "grocery": 3,
    "scheduling": 8,
}

# Expiration loop interval (seconds) — only scheduled loop on Executor
EXPIRATION_CHECK_INTERVAL = 900    # 15 minutes

# Minimum gap between escalation notifications per action
ESCALATION_COOLDOWN = 900

# Token limits
QA_MAX_TOKENS           = 300
MODIFICATION_MAX_TOKENS = 800

# Org context fields injected per domain
ORG_CONTEXT_MAP = {
    "health":      ["health_protocol", "care_philosophy",
                    "escalation_chain", "escalation_lead"],
    "appointment": ["transport_protocol", "visit_frequency_default",
                    "care_philosophy"],
    "grocery":     ["care_philosophy", "visit_frequency_default"],
    "financial":   ["financial_protocol", "escalation_lead"],
    "executor":    ["org_name", "escalation_lead", "escalation_chain"],
}

# Detection only fires on these triggers (no scheduled loops on supervisors)
DETECTION_TRIGGERS = ["patient_create", "patient_update"]

# Modification pipeline: health domain only in v1
# Future work: replicate to appointment, grocery, financial
MODIFICATION_ENABLED_DOMAINS = ["health"]

# Domains that may need Worker involvement for live API data
DOMAINS_WITH_LIVE_API = {
    "health":      ["OpenFDA drug status", "recall updates"],
    "appointment": ["Google Maps route refresh"],
    "grocery":     ["Instacart cart re-build"],
    "financial":   [],
}

DOMAIN_COLORS = {
    "health": "#EF4444", "appointment": "#3B82F6",
    "grocery": "#10B981", "financial": "#F59E0B", "scheduling": "#8B5CF6",
}

DOMAIN_SUPERVISOR_MAP = {
    # Set from env vars at agent startup
    "health":      None,   # os.environ["HEALTH_SUPERVISOR_ADDRESS"]
    "appointment": None,   # os.environ["APPT_SUPERVISOR_ADDRESS"]
    "grocery":     None,   # os.environ["GROCERY_SUPERVISOR_ADDRESS"]
    "financial":   None,   # os.environ["FINANCIAL_SUPERVISOR_ADDRESS"]
}
```

---

## 5. MOCK API ENDPOINTS

All implemented as FastAPI routers mounted under `/mock/`.

### 5.1 CVS Refill — `POST /mock/cvs/refill`

```json
Request:  { "medication": "Lisinopril 10mg", "patient_id": "pt_001", "pharmacy": "CVS Mission St" }
Response: { "status": "accepted", "confirmation_id": "CVS-{date}-{6-digit-random}",
            "estimated_ready": "{tomorrow}T14:00:00Z", "pharmacy_phone": "+1-555-0288",
            "pharmacist_name": "David Nguyen", "notes": "Refill authorized." }
```

Generate `confirmation_id` as `CVS-{YYYYMMDD}-{random 6 digits}`.
Always return `status: "accepted"` unless medication field is empty (return 400).

### 5.2 Cal.com Booking — `POST /mock/cal/book`

```json
Request:  { "provider": "Dr. Anita Patel", "patient_id": "pt_001", "preferred_times": ["morning"] }
Response: { "status": "booked", "confirmation_id": "CAL-{date}-{6-digit-random}",
            "appointment_datetime": "{next-business-day}T10:00:00Z",
            "location": "400 Parnassus Ave, SF CA 94143",
            "provider_confirmation_sent": true,
            "notes": "Morning slot confirmed. Bring current medication list." }
```

`appointment_datetime` = next business day from request time at 10:00am.

### 5.3 Instacart — `POST /mock/instacart/cart`

```json
Request:  { "patient_id": "pt_001", "items": ["spinach", "chicken breast"],
            "dietary_flags": ["low sodium"] }
Response: { "status": "cart_created", "cart_id": "INST-{date}-{6-digit-random}",
            "estimated_delivery": "{tomorrow}T11:00:00Z", "total_estimate": 38.74,
            "items_confirmed": ["spinach 1lb", "chicken breast 2lb"],
            "dietary_verified": true, "store": "Safeway Mission St" }
```

### 5.4 Amazon Reorder — `POST /mock/amazon/reorder`

```json
Request:  { "patient_id": "pt_001", "items": [{ "name": "adult briefs", "qty": 2 }] }
Response: { "status": "order_placed", "order_id": "AMZ-{date}-{6-digit-random}",
            "estimated_delivery": "{day-after-tomorrow}T18:00:00Z", "total": 24.99,
            "items": [{ "name": "adult briefs size M", "qty": 2, "unit_price": 12.49 }],
            "prime_delivery": true }
```

### 5.5 Caregiver Availability — `POST /mock/caregivers/available`

Reads live from SQLite `caregiver_schedule` table — data is real and dynamic.

```json
Request: { "date": "2026-04-28", "manual_action_type": "transport",
           "patient_id": "pt_001", "duration_hours": 2.0 }

Response: {
  "available_caregivers": [
    { "caregiver_id": "cg_001", "name": "Sarah Okafor",
      "email": "sarah@sunrisecare.org", "date": "2026-04-28",
      "start_time": "08:00", "end_time": "16:00",
      "assigned_to_patient": true,
      "slot_label": "Mon Apr 28 · 8:00am–4:00pm" },
    { "caregiver_id": "cg_004", "name": "Marcus Webb",
      "date": "2026-04-28", "start_time": "10:00", "end_time": "18:00",
      "assigned_to_patient": false,
      "slot_label": "Mon Apr 28 · 10:00am–6:00pm" }
  ],
  "date_checked": "2026-04-28",
  "total_available": 2
}
```

Query: `WHERE date=request.date AND available=1 AND booked=0`.
Sort: assigned_to_patient caregivers first, then by start_time.
If no caregivers available on requested date, try next 3 business days
and return first date with availability.

---

## 6. AGENT IMPLEMENTATIONS

### 6.1 Detection Model — Event-Driven

Detection is triggered only by patient_create or patient_update events.
Domain Supervisors have **no `@on_interval` handlers** — they are purely
message-driven. The Executor calls them on-demand via `run_detection()`.

```python
# In executor/agent.py
async def run_detection(ctx: Context, patient_id: str,
                        trigger: str, updated_domain: str = None):
    """
    Called immediately after patient_create or patient_update.
    Broadcasts OnDemandDetectionRequest to all 4 domain supervisors.
    """
    org = db.get_org_profile()
    pass_id = str(uuid4())
    for domain, supervisor_addr in DOMAIN_SUPERVISOR_MAP.items():
        org_context = { k: org.get(k) for k in ORG_CONTEXT_MAP[domain] }
        await ctx.send(supervisor_addr, OnDemandDetectionRequest(
            patient_id=patient_id,
            trigger=trigger,
            pass_id=pass_id,
            updated_domain=updated_domain,
            org_context=org_context
        ))
```

### 6.2 Domain Supervisors — Base Handler (all 4 domains)

Each Domain Supervisor implements this handler. No `@on_interval` exists on any supervisor.

```python
@agent.on_message(model=OnDemandDetectionRequest)
async def on_detection_request(ctx: Context, sender: str,
                                msg: OnDemandDetectionRequest):
    org_context = msg.org_context  # Do not re-query DB — use msg value

    # Dispatch to Worker with patient context
    await ctx.send(WORKER_ADDR, DetectionRequest(
        patient_ids=[msg.patient_id],
        pass_id=msg.pass_id,
        org_context=org_context
    ))
```

All LLM calls in Supervisors and Workers use `build_system_prompt()` to inject
org context. Example pattern:

```python
system = build_system_prompt(
    base_prompt="Draft a professional medication refill request...",
    org_context=org_context,
    domain="health"
)
```

### 6.3 Health Worker — Detection Checks

Receives `DetectionRequest`. For each patient_id, reads Life Graph from SQLite.

**Check 1 — Refill due**
```
days_until_due = (refill_due - today).days
if days_until_due <= 5 AND no adherence gap > 2 in last 7 days:
    draft ActionDraft(
        type="automated_task", urgency_level="tier_2",
        review_by=now + REVIEW_BY_HOURS["tier_2"],
        draft_content=LLM refill email,
        recipient_type="pharmacy",
        api_payload={ medication, patient_id, pharmacy }
    )
```

LLM prompt (refill email):
```
System: [build_system_prompt applied]
        Draft a professional medication refill request email on behalf of a caregiver.
        Return the email body only — no subject, no preamble.
User:   Patient: {name}, {age}. Medication: {med_name} {dosage}, {frequency}.
        Prescriber: {prescriber}. Last refill: {last_refill}.
        Supply: {days_supply} days. Refill due: {refill_due}.
        Draft a polite, concise refill request to {pharmacy}.
```

**Check 2 — Missed dose + worsening notes**
```
consecutive_gap = longest run of missing dates in adherence_log (last 14 days)
if consecutive_gap >= 3:
    assessment = call_claude_json(note_assessment_prompt, notes_last_7_days)
    if assessment["assessment"] == "worsening":
        draft ActionDraft(
            type="manual_approval", urgency_level="tier_1",
            review_by=now + REVIEW_BY_HOURS["tier_1"],
            draft_content=LLM escalation email,
            recipient_type="prescriber"
        )
```

LLM prompt (note assessment):
```
System: Assess caregiver notes for a senior care escalation system.
        Return JSON only: { "assessment": "worsening"|"stable", "reason": "..." }
User:   Patient: {name}. Notes from last 7 days: {notes}
```

LLM prompt (escalation email):
```
System: [build_system_prompt applied]
        Draft a clinical escalation email from caregiver to prescribing physician.
        Professional, factual, urgent. Return email body only.
User:   Patient: {name}, {age}. Medication: {med_name} {dosage}.
        Missed {gap} consecutive days. Recent notes: {notes}.
        Draft escalation to {prescriber}.
```

**Check 3 — OpenFDA drug interaction (REAL API)**
```
For each pair of co-prescribed medications:
    GET https://api.fda.gov/drug/label.json
        ?search=openfda.generic_name:"{drug_name}"&limit=1
    Cross-reference drug_interactions field for mentions of other drugs
if interaction found:
    draft ActionDraft(
        type="manual_approval", urgency_level="tier_1",
        review_by=now + REVIEW_BY_HOURS["tier_1"],
        draft_content=LLM FDA interaction email to prescriber
    )
```

**Check 4 — OpenFDA recall (REAL API)**
```
For each medication:
    GET https://api.fda.gov/drug/enforcement.json
        ?search=product_description:"{drug_name}"&limit=5
    Filter for status == "Ongoing"
if recall found:
    draft ActionDraft(
        type="manual_approval", urgency_level="tier_0",
        review_by=now + REVIEW_BY_HOURS["tier_0"],
        draft_content=LLM urgent recall notification
    )
```

Return `WorkerResult` to Health Supervisor.

### 6.4 Health Supervisor — Detection Risk Scoring

Receives `WorkerResult`. For each draft:

1. Read full Life Graph from SQLite
2. LLM risk scoring pass:
```
System: [build_system_prompt applied]
        Assess urgency for a senior care action. Return JSON only:
        { "urgency_level": "tier_0"|"tier_1"|"tier_2"|"tier_3",
          "framing": "One-sentence dashboard description",
          "caregiver_instruction": "What caregiver should do" }
User:   Patient: {name}, {age}. Domain: health.
        Action: {description}. Draft: {draft_content}.
        Medications: {meds}. Recent notes: {notes_last_7_days}.
```
3. Override `urgency_level` if LLM assesses higher than Worker's initial level
4. Set `review_by = invocation_date + REVIEW_BY_HOURS[urgency_level]`
5. Write to `action_history` via `db.write_action()`
6. Return `SupervisorResult` to Executor

### 6.5 Health Supervisor — Modification Pipeline (health only)

**Handler A — ModificationRequest**

```python
@agent.on_message(model=ModificationRequest)
async def on_modification_request(ctx: Context, sender: str, msg: ModificationRequest):
    life_graph = db.get_patient(msg.patient_id)
    requires_live_api = assess_requires_live_api(msg.modification_instruction, msg.domain)
    # Keyword check (no LLM): "FDA", "recall", "current status" → True; else False

    if requires_live_api:
        ctx.storage.set(f"mod_pending_{msg.action_id}", msg.json())
        await ctx.send(WORKER_ADDR, ModificationTask(
            action_id=msg.action_id, patient_id=msg.patient_id,
            domain=msg.domain, action_type=msg.action_type,
            current_draft=msg.current_draft,
            modification_instruction=msg.modification_instruction,
            requires_live_api=True,
            api_context=identify_api_context(msg.modification_instruction, msg.domain)
        ))
        return

    revised_draft = draft_revision(msg, life_graph)
    review_passed = review_revision(msg.current_draft, revised_draft,
                                    msg.modification_instruction)
    if not review_passed:
        revised_draft = draft_revision(msg, life_graph, retry=True)

    await ctx.send(sender, ModificationResult(
        action_id=msg.action_id, patient_id=msg.patient_id,
        revised_draft=revised_draft,
        changes_summary=summarise_changes(msg.current_draft, revised_draft)
    ))

def draft_revision(msg: ModificationRequest, life_graph: dict,
                   retry: bool = False) -> str:
    retry_prefix = "Previous attempt was insufficient. " if retry else ""
    system = build_system_prompt(
        f"{retry_prefix}You are revising a care action draft based on a caregiver's "
        "modification request. Apply the requested change precisely. Preserve all "
        "clinical details not mentioned in the request. Return revised draft text only.",
        org_context=db.get_org_profile(), domain=msg.domain
    )
    user = (f"Patient: {life_graph['name']}, {life_graph['age']}.\n"
            f"Modification requested: {msg.modification_instruction}\n\n"
            f"Current draft:\n{msg.current_draft}\n\nReturn the revised draft only.")
    return call_claude(system, user, max_tokens=MODIFICATION_MAX_TOKENS)

def review_revision(original: str, revised: str, instruction: str) -> bool:
    system = ("Review a draft revision. Return JSON only: { 'passed': bool, 'reason': str }. "
              "Pass if: (1) requested change is applied, (2) no clinical info was lost, "
              "(3) draft remains professional.")
    result = call_claude_json(system,
        f"Instruction: {instruction}\nOriginal: {original}\nRevised: {revised}")
    return result.get("passed", False)

def summarise_changes(original: str, revised: str) -> str:
    system = "Summarise what changed between two drafts in one concise sentence. Return the sentence only."
    return call_claude(system, f"Original:\n{original}\n\nRevised:\n{revised}", max_tokens=80)
```

**Handler B — ModificationDraft from Worker**

```python
@agent.on_message(model=ModificationDraft)
async def on_modification_draft(ctx: Context, sender: str, msg: ModificationDraft):
    original_msg_json = ctx.storage.get(f"mod_pending_{msg.action_id}")
    original_msg = ModificationRequest.parse_raw(original_msg_json)
    ctx.storage.remove(f"mod_pending_{msg.action_id}")

    review_passed = review_revision(original_msg.current_draft,
                                    msg.revised_draft,
                                    original_msg.modification_instruction)
    if not review_passed:
        life_graph = db.get_patient(original_msg.patient_id)
        revised_draft = draft_revision(original_msg, life_graph, retry=True)
    else:
        revised_draft = msg.revised_draft

    await ctx.send(EXECUTOR_ADDR, ModificationResult(
        action_id=msg.action_id, patient_id=original_msg.patient_id,
        revised_draft=revised_draft, changes_summary=msg.changes_summary
    ))
```

### 6.6 Domain Supervisors — Q&A Pipeline (all 4 domains)

**Handler C — QuestionRequest**

```python
@agent.on_message(model=QuestionRequest)
async def on_question_request(ctx: Context, sender: str, msg: QuestionRequest):
    # Keywords that imply live API needed: "current", "latest", "still", "now",
    # "today", "updated" combined with domain API terms
    requires_live_api = question_requires_live_api(msg.question, msg.domain)

    if requires_live_api:
        ctx.storage.set(f"qa_pending_{msg.action_id}", msg.json())
        await ctx.send(WORKER_ADDR, QuestionTask(
            action_id=msg.action_id, patient_id=msg.patient_id,
            domain=msg.domain, question=msg.question,
            api_lookup_instruction=identify_api_lookup(msg.question, msg.domain)
        ))
        return

    answer = answer_question(msg)
    await ctx.send(sender, QuestionAnswer(
        action_id=msg.action_id, answer=answer,
        requires_action=False, suggested_action=None
    ))

def answer_question(msg: QuestionRequest) -> str:
    system = build_system_prompt(
        "You are a clinical care coordinator answering a caregiver's question "
        "about a specific care action. Be concise (2–4 sentences max). Be precise. "
        "Do not hedge unless genuinely uncertain. Do not repeat the question.",
        org_context=db.get_org_profile(), domain=msg.domain
    )
    user = (f"Domain: {msg.domain}. Action type: {msg.action_type}.\n"
            f"Question: {msg.question}\n\n"
            f"Current draft:\n{msg.current_draft or '(no draft)'}\n\n"
            f"Patient Life Graph:\n{msg.life_graph_snapshot}\n\n"
            "Answer the question directly and concisely.")
    return call_claude(system, user, max_tokens=QA_MAX_TOKENS)
```

**Handler D — QuestionApiResult from Worker**

```python
@agent.on_message(model=QuestionApiResult)
async def on_question_api_result(ctx: Context, sender: str, msg: QuestionApiResult):
    original_msg_json = ctx.storage.get(f"qa_pending_{msg.action_id}")
    original_msg = QuestionRequest.parse_raw(original_msg_json)
    ctx.storage.remove(f"qa_pending_{msg.action_id}")

    system = build_system_prompt(
        "You are a clinical care coordinator. Answer the caregiver's question "
        "using the patient data and fresh API data provided. Be concise (2–4 sentences max).",
        org_context=db.get_org_profile(), domain=original_msg.domain
    )
    user = (f"Question: {original_msg.question}\n"
            f"Patient: {original_msg.life_graph_snapshot}\n"
            f"Fresh data from {original_msg.domain} API: {msg.api_data}\n"
            "Answer concisely.")
    answer = call_claude(system, user, max_tokens=QA_MAX_TOKENS)

    await ctx.send(EXECUTOR_ADDR, QuestionAnswer(
        action_id=original_msg.action_id, answer=answer,
        requires_action=False, suggested_action=None
    ))
```

### 6.7 Appointment Worker — Detection Checks

**Check 1 — Overdue appointment**
```
months_since = (today - last_visit).days / 30
if months_since > recommended_frequency_months:
    draft ActionDraft(
        type="manual_approval", urgency_level="tier_1",
        draft_content=LLM scheduling message to clinic
    )
```

**Check 2 — Transport planning (Google Maps REAL API)**
```
Only fires when next_scheduled is set AND within 7 days.
GET https://maps.googleapis.com/maps/api/distancematrix/json
    ?origins={patient_address}&destinations={clinic_address}&key={KEY}

departure_time = appointment_datetime - travel_duration - 15min buffer

draft ActionDraft(
    type="scheduling_task", manual_action_type="transport",
    urgency_level="tier_1",
    description="Transport: {patient} → {clinic} on {date} at {time}",
    draft_content=JSON.dumps({ distance, duration, departure_time,
                               appointment_datetime, clinic_address })
)
```

**Check 3 — Visit prep summary**
```
Fires when next_scheduled within 3 days.
LLM synthesises from Life Graph: medications, recent notes, last visit context.
draft ActionDraft(type="manual_approval", urgency_level="tier_2",
    draft_content=LLM visit prep summary)
```

**Check 4 — Post-visit extraction**
```
Fires when Executor forwards a caregiver message with provider instructions.
LLM parses into structured tasks → writes to Life Graph.
draft ActionDraft(type="automated_task", urgency_level="tier_3",
    description="Post-visit instructions extracted and saved")
```

### 6.8 Grocery Worker — Detection Checks

**Check 1 — Delivery staleness**
```
days_since = (today - last_delivery).days
max_freq = max(staple.frequency_days for staple in staples)
if days_since > max_freq:
    cart_response = POST /mock/instacart/cart { patient_id, items, dietary_flags }
    draft ActionDraft(
        type="scheduling_task", manual_action_type="grocery_delivery",
        urgency_level="tier_2",
        draft_content=formatted cart summary,
        api_payload=instacart request body
    )
```

**Check 2 — Dietary conflict**
```
Fires when Executor forwards a meal log from caregiver.
LLM checks meal against dietary_restrictions.
if conflict:
    draft ActionDraft(type="automated_task", urgency_level="tier_0",
        description="Dietary conflict: {meal} conflicts with {restriction}")
```

**Check 3 — Supply reorder**
```
Fires on caregiver supply flag via ASI:One.
draft ActionDraft(
    type="scheduling_task", manual_action_type="supply_reorder",
    urgency_level="tier_2", api_payload=amazon reorder body
)
```

### 6.9 Financial Worker — Detection Checks

**Check 1 — Bill due alert**
```
for bill in bills:
    days_until = (due_date - today).days
    if days_until <= 5 AND NOT autopay:
        draft ActionDraft(
            type="automated_task",
            urgency_level="tier_1" if days_until <= 2 else "tier_2",
            description="{name} due in {days} days — ${amount} — autopay OFF"
        )
```

**Check 2 — Missed autopay**
```
for bill in bills where autopay=True:
    if due_date < today AND no completion record in action_history:
        draft ActionDraft(type="automated_task", urgency_level="tier_1",
            description="Autopay may have failed: {name} ${amount}")
```

**Check 3 — Anomaly detection**
```
LLM compares current bills vs anomalies baseline:
System: Detect financial anomalies for senior care.
        Return JSON: { "anomaly_detected": bool, "description": str,
                       "severity": "low"|"medium"|"high" }
User:   Bills: {bills_json}. Historical: {anomalies_json}.
        Flag charges >20% above typical.
if anomaly_detected:
    draft ActionDraft(
        type="automated_task",
        urgency_level="tier_1" if severity=="high" else "tier_2",
        description="Unusual charge: {description}"
    )
```

### 6.10 Appointment, Grocery, Financial Supervisors

Same detection risk-scoring pattern as Health Supervisor (section 6.4).
All implement Q&A handlers (sections 6.6 Handler C and D).
**None implement modification handlers** — modification is health domain only.
Scheduling tasks (`manual_action_type` set) propagate with
`scheduling_status="pending_approval"`.

### 6.11 Domain Workers — Modification and Q&A handlers

**Modification Task Handler (Health Worker only)**

```python
@agent.on_message(model=ModificationTask)
async def on_modification_task(ctx: Context, sender: str, msg: ModificationTask):
    patient = db.get_patient(msg.patient_id)
    api_data = fetch_live_data(msg.domain, msg.api_context, patient)

    system = build_system_prompt(
        "Revise this care action draft incorporating the live API data provided. "
        "Apply the modification instruction precisely. Return revised draft text only.",
        org_context=db.get_org_profile(), domain=msg.domain
    )
    user = (f"Modification: {msg.modification_instruction}\n"
            f"Live data: {api_data}\n"
            f"Current draft: {msg.current_draft}\n"
            "Return revised draft only.")
    revised = call_claude(system, user, max_tokens=MODIFICATION_MAX_TOKENS)

    await ctx.send(sender, ModificationDraft(
        action_id=msg.action_id,
        revised_draft=revised,
        changes_summary=summarise_changes(msg.current_draft, revised)
    ))

def fetch_live_data(domain: str, api_context: str, patient: dict) -> str:
    if domain == "health" and "FDA" in (api_context or ""):
        med_name = patient["medications"][0]["name"]
        r = httpx.get(f"https://api.fda.gov/drug/label.json"
                      f"?search=openfda.generic_name:\"{med_name}\"&limit=1")
        return r.text
    elif domain == "appointment" and "Maps" in (api_context or ""):
        r = httpx.get("https://maps.googleapis.com/maps/api/distancematrix/json",
            params={"origins": patient["address"],
                    "destinations": patient["appointments"][0]["clinic_address"],
                    "key": os.environ["GOOGLE_MAPS_API_KEY"]})
        return r.text
    elif domain == "grocery" and "Instacart" in (api_context or ""):
        r = httpx.post(f"{MOCK_API_BASE}/mock/instacart/cart", json={
            "patient_id": patient["patient_id"],
            "items": [s["item"] for s in patient["grocery"]["staples"]],
            "dietary_flags": patient["grocery"]["dietary_restrictions"]
        })
        return r.text
    return ""
```

**Q&A Task Handler (all domain Workers)**

```python
@agent.on_message(model=QuestionTask)
async def on_question_task(ctx: Context, sender: str, msg: QuestionTask):
    patient = db.get_patient(msg.patient_id)
    api_data = fetch_live_data(msg.domain, msg.api_lookup_instruction, patient)
    await ctx.send(sender, QuestionApiResult(
        action_id=msg.action_id,
        api_data=api_data
    ))
```

### 6.12 Executor Agent

```python
# ── Expiration loop — only scheduled loop remaining ───────────────────────────
@agent.on_interval(period=900.0)
async def expiration_check(ctx: Context):
    overdue = db.get_overdue_actions()
    for action in overdue:
        db.mark_action_overdue(action["action_id"])

        # ASI:One push (skipped if asi_one_address is None)
        if action.get("assigned_caregiver"):
            caregiver = db.get_caregiver(action["assigned_caregiver"])
            if (caregiver and caregiver.get("asi_one_address")
                    and not db.has_been_notified(action["action_id"], "asi_one")):
                await ctx.send(caregiver["asi_one_address"],
                    ChatMessage(content=build_overdue_message(action, caregiver)))
                db.log_expiration_notification(action["action_id"], "asi_one")

        # Dashboard notification
        if not db.has_been_notified(action["action_id"], "dashboard"):
            db.write_notification(
                type="overdue", action_id=action["action_id"],
                patient_id=action["patient_id"],
                title="⏰ Action overdue",
                body=f"{action.get('patient_name','Patient')} · "
                     f"{action['domain']} · {action['description']}"
            )
            db.log_expiration_notification(action["action_id"], "dashboard")

def build_overdue_message(action: dict, caregiver: dict) -> str:
    return (
        f"⚠️ OVERDUE — Action requires immediate attention.\n"
        f"Patient: {action.get('patient_name', action['patient_id'])}. "
        f"Task: {action['description']}. "
        f"Was due: {action['review_by']}. "
        f"Please resolve in the MACOS dashboard immediately."
    )


# ── On-demand detection — called from FastAPI via internal HTTP ───────────────
async def run_detection(ctx: Context, patient_id: str,
                        trigger: str, updated_domain: str = None):
    org = db.get_org_profile()
    pass_id = str(uuid4())
    for domain, addr in DOMAIN_SUPERVISOR_MAP.items():
        org_context = { k: org.get(k) for k in ORG_CONTEXT_MAP[domain] }
        await ctx.send(addr, OnDemandDetectionRequest(
            patient_id=patient_id, trigger=trigger,
            pass_id=pass_id, updated_domain=updated_domain,
            org_context=org_context
        ))

# FastAPI calls this internal endpoint to trigger detection:
# POST http://localhost:8001/internal/detect
# Body: { "patient_id": str, "trigger": str, "updated_domain": str|null }


# ── SupervisorResult handler ──────────────────────────────────────────────────
@agent.on_message(model=SupervisorResult)
async def on_supervisor_result(ctx: Context, sender: str, msg: SupervisorResult):
    # Actions already written to action_history by domain supervisors.
    # Route scheduling_task actions to Scheduling Agent (pending_approval state).
    for action in msg.actions:
        if action.type == "scheduling_task":
            db.update_action(action.action_id, {"scheduling_status": "pending_approval"})
    # Rankings computed live by get_action_rankings() — no separate write needed.


# ── Intent classifier ─────────────────────────────────────────────────────────
def classify_intent(text: str, action_id: str | None) -> str:
    mod_keywords   = ["change", "modify", "update", "make it", "rewrite", "add",
                      "remove", "replace", "adjust", "revise", "edit"]
    q_keywords     = ["why", "what", "how", "when", "is", "does", "explain",
                      "tell me", "what does", "what is", "?"]
    sched_keywords = ["who can", "assign", "caregiver", "schedule", "transport"]
    onboard_keywords = ["new patient", "adding", "onboard"]

    text_lower = text.lower()
    if any(k in text_lower for k in onboard_keywords): return "onboarding"
    if any(k in text_lower for k in sched_keywords):   return "scheduling"

    if action_id:
        system = ("Classify this message as exactly one of:\n"
                  "'modification' — user wants to change an existing draft\n"
                  "'question' — user wants information about the action\n"
                  "Return JSON only: { \"intent\": \"modification\"|\"question\" }")
        result = call_claude_json(system, text, max_tokens=50)
        return result.get("intent", "question")

    if any(k in text_lower for k in mod_keywords): return "modification"
    if any(k in text_lower for k in q_keywords):   return "question"
    return "general"


# ── ASI:One / Dashboard chat handler ─────────────────────────────────────────
@agent.on_message(model=ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    action_id  = getattr(msg, 'action_id', None)
    patient_id = getattr(msg, 'patient_id', None)
    intent = classify_intent(msg.content, action_id)

    if intent == "onboarding":
        await handle_onboarding(ctx, sender, msg)
    elif intent == "scheduling":
        await handle_scheduling_query(ctx, sender, msg)
    elif intent == "modification" and action_id:
        await handle_modification(ctx, sender, msg, action_id, patient_id)
    elif intent == "question" and action_id:
        await handle_question(ctx, sender, msg, action_id, patient_id)
    else:
        await handle_general_query(ctx, sender, msg)


# ── Modification handler ──────────────────────────────────────────────────────
async def handle_modification(ctx, sender, msg, action_id: str, patient_id: str):
    action = db.get_action(action_id)
    if not action:
        db.write_chat_message(action_id, "agent",
            "Action not found. Please refresh the dashboard.")
        return

    if action["domain"] not in MODIFICATION_ENABLED_DOMAINS:
        db.write_chat_message(action_id, "agent",
            f"Modification is not yet supported for {action['domain']} actions. "
            "You can still ask questions about this action.")
        return

    if action["type"] == "scheduling_task":
        db.write_chat_message(action_id, "agent",
            "Scheduling tasks can't be modified via chat — "
            "use 'Go to Scheduling →' to reassign.")
        return

    db.write_chat_message(action_id, "user", msg.content, intent="modification")
    db.set_modification_in_progress(action_id, True)
    db.write_chat_message(action_id, "agent",
        "Updating draft — this will take a moment...", intent=None)

    life_graph = db.serialize_life_graph(patient_id)
    await ctx.send(DOMAIN_SUPERVISOR_MAP["health"], ModificationRequest(
        action_id=action_id, patient_id=patient_id,
        domain=action["domain"], action_type=action["type"],
        current_draft=action["draft_content"] or "",
        modification_instruction=msg.content,
        life_graph_snapshot=json.dumps(life_graph)
    ))


# ── ModificationResult handler ────────────────────────────────────────────────
@agent.on_message(model=ModificationResult)
async def on_modification_result(ctx: Context, sender: str, msg: ModificationResult):
    action = db.get_action(msg.action_id)
    db.replace_draft(msg.action_id, msg.revised_draft)
    db.write_chat_message(msg.action_id, "agent",
        f"Done. {msg.changes_summary} The draft has been updated above.", intent=None)
    patient = db.get_patient(msg.patient_id)
    db.write_notification(
        type="modification_complete", action_id=msg.action_id,
        patient_id=msg.patient_id, title="Draft updated",
        body=f"{patient['name']} · {action['domain'].capitalize()} · {msg.changes_summary}"
    )


# ── Question handler ──────────────────────────────────────────────────────────
async def handle_question(ctx, sender, msg, action_id: str, patient_id: str):
    action = db.get_action(action_id)
    if not action:
        db.write_chat_message(action_id, "agent", "Action not found.")
        return

    db.write_chat_message(action_id, "user", msg.content, intent="question")
    db.write_chat_message(action_id, "agent", "Looking into this...", intent=None)

    life_graph = db.serialize_life_graph(patient_id)
    await ctx.send(DOMAIN_SUPERVISOR_MAP[action["domain"]], QuestionRequest(
        action_id=action_id, patient_id=patient_id,
        domain=action["domain"], action_type=action["type"],
        question=msg.content,
        current_draft=action.get("draft_content"),
        life_graph_snapshot=json.dumps(life_graph)
    ))


# ── QuestionAnswer handler ────────────────────────────────────────────────────
@agent.on_message(model=QuestionAnswer)
async def on_question_answer(ctx: Context, sender: str, msg: QuestionAnswer):
    db.replace_last_agent_message(msg.action_id, msg.answer)
    if msg.requires_action and msg.suggested_action:
        db.write_chat_message(msg.action_id, "agent",
            f"Note: {msg.suggested_action}", intent=None)


# ── Onboarding handler ────────────────────────────────────────────────────────
async def handle_onboarding(ctx, sender, msg):
    org = db.get_org_profile()
    system = build_system_prompt(
        """Extract patient data from a caregiver's message.
Return JSON only matching this schema:
{ patient_id, name, age, address,
  medications: [...], appointments: [...],
  grocery: {...}, emergency_contacts: [...] }
Generate patient_id as "pt_" + 3 random digits if not provided.
Use null for any missing fields. Do not invent data.""",
        org_context=org, domain="health"
    )
    extracted = call_claude_json(system, msg.content)
    patient_id = db.write_patient(extracted)
    # Trigger detection
    import httpx
    httpx.post(f"{EXECUTOR_INTERNAL_URL}/internal/detect",
        json={"patient_id": patient_id, "trigger": "patient_create"})
    # Respond
    pending = db.get_pending_actions(patient_id=patient_id)
    flags = [a["description"] for a in pending]
    reply = f"Got it — {extracted.get('name', 'Patient')} added."
    if flags:
        reply += f" Immediate flags: {'; '.join(flags)}."
    await ctx.send(sender, ChatMessage(content=reply))


# ── Scheduling query handler ──────────────────────────────────────────────────
async def handle_scheduling_query(ctx, sender, msg):
    pending_scheduling = [a for a in db.get_pending_actions()
                          if a["type"] == "scheduling_task"
                          and a["scheduling_status"] == "pending_approval"]
    if not pending_scheduling:
        await ctx.send(sender, ChatMessage(
            content="No scheduling tasks are currently pending."))
        return
    target = pending_scheduling[0]
    await ctx.send(SCHEDULING_AGENT_ADDR, SchedulingQuery(
        action_id=target["action_id"], patient_id=target["patient_id"],
        manual_action_type=target["manual_action_type"],
        description=target["description"],
        required_date=None, requester_address=sender
    ))


# ── General query handler ─────────────────────────────────────────────────────
async def handle_general_query(ctx, sender, msg):
    org = db.get_org_profile()
    pending = db.get_pending_actions()
    patients = db.get_all_patients()
    system = build_system_prompt(
        "You are a care coordinator assistant. Answer the caregiver's question "
        "based on the patient data and pending actions provided. Be concise and clinical.",
        org_context=org, domain="executor"
    )
    answer = call_claude(system,
        f"Question: {msg.content}\n\nPending: {pending}\n\nPatients: {patients}")
    await ctx.send(sender, ChatMessage(content=answer))
```

### 6.13 Scheduling Agent

```python
@agent.on_message(model=SchedulingQuery)
async def on_scheduling_query(ctx: Context, sender: str, msg: SchedulingQuery):
    target_date = msg.required_date or next_business_day()
    response = httpx.post(f"{MOCK_API_BASE}/mock/caregivers/available", json={
        "date": target_date, "manual_action_type": msg.manual_action_type,
        "patient_id": msg.patient_id, "duration_hours": 2.0
    })
    available = response.json()["available_caregivers"]

    if not available:
        await ctx.send(msg.requester_address, ChatMessage(
            content=f"No caregivers available around {target_date}. "
                    "Try a different date via the dashboard."))
        return

    db.update_action(msg.action_id, {"caregiver_options_json": json.dumps(available)})

    lines = [f"Available caregivers for: {msg.description}\n"]
    for i, c in enumerate(available, 1):
        star = " ★ (assigned to patient)" if c["assigned_to_patient"] else ""
        lines.append(f"{i}. {c['name']}{star} — {c['slot_label']}")
    lines.append("\nReply with the number to assign (e.g. '1') or 'cancel'.")
    await ctx.send(msg.requester_address, ChatMessage(content="\n".join(lines)))


@agent.on_message(model=ChatMessage)
async def on_caregiver_reply(ctx: Context, sender: str, msg: ChatMessage):
    text = msg.content.strip()
    if text.lower() == "cancel":
        await ctx.send(sender, ChatMessage(content="Scheduling cancelled."))
        return

    try:
        idx = int(text) - 1
    except ValueError:
        await ctx.send(sender, ChatMessage(
            content="Reply with a number from the list, or 'cancel'."))
        return

    action = db.get_latest_pending_scheduling_action()
    if not action:
        return

    options = json.loads(action["caregiver_options_json"])
    if idx < 0 or idx >= len(options):
        await ctx.send(sender, ChatMessage(content="Invalid selection. Try again."))
        return

    selected = options[idx]
    db.update_action(action["action_id"], {
        "assigned_caregiver": selected["caregiver_id"],
        "scheduling_status": "unconfirmed",
        "reviewed": 0
    })
    db.book_caregiver_slot(selected["caregiver_id"], selected["date"])
    db.write_notification(
        type="scheduling_update", action_id=action["action_id"],
        patient_id=action["patient_id"], title="Scheduling task assigned",
        body=f"{selected['name']} assigned — awaiting confirmation"
    )
    await ctx.send(sender, ChatMessage(
        content=f"✓ {selected['name']} has been assigned. "
                "The task is in their dashboard awaiting confirmation."))
```

---

## 7. UPDATE PATIENT PIPELINE

### 7.1 Overview

Caregivers can modify existing patient Life Graph data via a conversational
slide-in panel in the Patient Roster view. Supports free text, PDF, and image
input. Every change requires explicit caregiver confirmation before any DB write.
After write, detection is triggered immediately via the Executor internal endpoint.

### 7.2 `POST /patients/{id}/update`

```python
class PatientUpdateRequest(BaseModel):
    content: str
    caregiver_id: str

@router.post("/{patient_id}/update")
async def update_patient(patient_id: str, body: PatientUpdateRequest):
    life_graph = db.serialize_life_graph(patient_id)
    org = db.get_org_profile()
    classification = classify_patient_update(body.content, life_graph, org)
    update_id = db.write_patient_update({
        "patient_id": patient_id, "caregiver_id": body.caregiver_id,
        "domain": classification["domain"],
        "operation": classification["operation"],
        "fields_changed": json.dumps(classification["fields_changed"]),
        "summary": classification["summary"],
        "confirmed": 0, "applied": 0,
    })
    return {
        "update_id": update_id,
        "summary": classification["summary"],
        "domain": classification["domain"],
        "operation": classification["operation"],
        "fields_changed": classification["fields_changed"],
        "proposed_changes": classification["proposed_changes"],
        "requires_confirmation": True
    }

def classify_patient_update(content: str, life_graph: dict, org: dict) -> dict:
    system = build_system_prompt(
        """You are classifying a caregiver's patient update request.
Return JSON only:
{
  "domain": "health"|"appointment"|"grocery"|"financial"|"general",
  "operation": "add"|"update"|"remove",
  "fields_changed": ["list", "of", "field", "names"],
  "summary": "One plain-language sentence describing the change",
  "risk_level": "low"|"medium"|"high",
  "proposed_changes": { /* structured dict of changes to Life Graph */ }
}""",
        org_context=org, domain="health"
    )
    user = f"Caregiver update: {content}\n\nCurrent patient data:\n{json.dumps(life_graph, indent=2)}"
    return call_claude_json(system, user, max_tokens=600)
```

### 7.3 `POST /patients/{id}/update/{update_id}/confirm`

```python
@router.post("/{patient_id}/update/{update_id}/confirm")
async def confirm_patient_update(patient_id: str, update_id: int):
    update = db.get_patient_update(update_id)
    if not update or update["applied"]:
        raise HTTPException(404, "Update not found or already applied")

    db.apply_patient_update(update_id, update["proposed_changes"])
    # apply_patient_update sets active=0 for removals — NEVER issues DELETE

    httpx.post(f"{EXECUTOR_INTERNAL_URL}/internal/detect", json={
        "patient_id": patient_id,
        "trigger": "patient_update",
        "updated_domain": update["domain"]
    })
    return { "status": "applied", "summary": update["summary"],
             "detection_triggered": True }
```

### 7.4 `POST /patients/{id}/update/file`

```python
@router.post("/{patient_id}/update/file")
async def update_patient_file(patient_id: str, file: UploadFile,
                               caregiver_id: str = Form(...)):
    content_bytes = await file.read()
    if file.content_type == "application/pdf":
        import pdfplumber, io
        with pdfplumber.open(io.BytesIO(content_bytes)) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages)
    elif file.content_type.startswith("image/"):
        import base64
        b64 = base64.standard_b64encode(content_bytes).decode()
        result = call_claude_vision(b64, file.content_type,
            "Extract all medical information visible in this image. "
            "Return JSON: { medication_name, dosage, frequency, prescriber, "
            "pharmacy, last_refill_date, days_supply, patient_name }. "
            "Use null for fields not visible.")
        text = json.dumps(result)
    else:
        raise HTTPException(400, "Unsupported file type")

    # Same classification + pending update flow as /update
    life_graph = db.serialize_life_graph(patient_id)
    org = db.get_org_profile()
    classification = classify_patient_update(text, life_graph, org)
    update_id = db.write_patient_update({
        "patient_id": patient_id, "caregiver_id": caregiver_id,
        "domain": classification["domain"],
        "operation": classification["operation"],
        "fields_changed": json.dumps(classification["fields_changed"]),
        "summary": classification["summary"],
        "confirmed": 0, "applied": 0,
    })
    return { "update_id": update_id, "summary": classification["summary"],
             "proposed_changes": classification["proposed_changes"],
             "requires_confirmation": True }
```

---

## 8. FASTAPI LAYER

### 8.1 `api/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import patients, actions, caregivers, scheduling, notifications, ingest, org
from .mock_apis import cvs, cal, instacart, amazon, caregivers as mock_caregivers

app = FastAPI(title="MACOS API")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"], allow_headers=["*"])

app.include_router(patients.router,         prefix="/patients")
app.include_router(actions.router,          prefix="/actions")
app.include_router(caregivers.router,       prefix="/caregivers")
app.include_router(scheduling.router,       prefix="/scheduling")
app.include_router(notifications.router,    prefix="/notifications")
app.include_router(ingest.router,           prefix="/ingest")
app.include_router(org.router,              prefix="/org")
app.include_router(cvs.router,              prefix="/mock/cvs")
app.include_router(cal.router,              prefix="/mock/cal")
app.include_router(instacart.router,        prefix="/mock/instacart")
app.include_router(amazon.router,           prefix="/mock/amazon")
app.include_router(mock_caregivers.router,  prefix="/mock/caregivers")
```

### 8.2 Patients Router

```
GET  /patients                             — list all active patients + urgency summary
GET  /patients/{id}                        — full Life Graph + pending + action history
POST /patients/{id}/update                 — submit update (returns pending for confirmation)
POST /patients/{id}/update/{uid}/confirm   — confirm + apply + trigger detection
POST /patients/{id}/update/file            — file-based update (same confirmation flow)
GET  /patients/{id}/update-history         — returns patient_updates rows newest first
```

**`GET /patients` response shape:**
```json
[{
  "patient_id": "pt_001", "name": "Margaret Chen", "age": 74,
  "urgency_level": "tier_0",
  "pending_action_count": 3,
  "overdue_action_count": 1,
  "assigned_caregivers": [
    { "caregiver_id": "cg_001", "name": "Sarah Okafor" }
  ]
}]
```

**`GET /patients/{id}` response shape:**
Returns `serialize_life_graph()` output plus:
```json
{
  "pending_actions": [...],
  "action_history": [...]
}
```

### 8.3 Actions Router

```
GET  /actions                    — ranked list (is_overdue first, then score)
POST /actions/{id}/approve       — execute action (Resend + mock API)
POST /actions/{id}/dismiss       — mark reviewed+completed, outcome="Dismissed"
POST /actions/{id}/chat          — send message; triggers intent classification
GET  /actions/{id}/chat-history  — returns action_chat rows for this action
```

**`GET /actions` query params:** `?domain=&urgency=&type=&patient_id=&is_overdue=`

**`GET /actions` response item shape:**
```json
{
  "action_id": "act_001", "patient_id": "pt_001", "patient_name": "Margaret Chen",
  "domain": "health", "type": "automated_task",
  "description": "Lisinopril refill 7 days overdue",
  "draft_content": "Dear CVS Mission St...",
  "draft_version": 1,
  "modification_in_progress": false,
  "urgency_level": "tier_2",
  "is_overdue": false,
  "review_by": "2026-04-25T09:00:00Z",
  "scheduling_status": null,
  "manual_action_type": null,
  "assigned_caregiver": null,
  "assigned_caregiver_name": null,
  "created_at": "2026-04-23T09:00:00Z"
}
```

**`POST /actions/{id}/chat` body:**
```python
class ActionChatRequest(BaseModel):
    content: str
    patient_id: str
    caregiver_id: str

# Implementation: write to action_chat, then POST to Executor internal endpoint
db.write_chat_message(action_id, "user", body.content, intent=None)
httpx.post(f"{EXECUTOR_INTERNAL_URL}/process-action-chat", json={
    "action_id": action_id,
    "patient_id": body.patient_id,
    "content": body.content
})
return { "status": "received" }
```

**`POST /actions/{id}/approve` implementation:**
```python
async def execute_approved_action(action_id: str):
    action = db.get_action(action_id)
    if action["domain"] == "health":
        if action.get("api_payload"):
            httpx.post(f"{MOCK_API_BASE}/mock/cvs/refill", json=action["api_payload"])
        send_resend_email(to=action["recipient_email"],
                          subject=build_subject(action),
                          body=action["draft_content"])
    elif action["domain"] == "appointment":
        send_resend_email(to=action["recipient_email"],
                          subject=build_subject(action),
                          body=action["draft_content"])
    elif action["domain"] == "grocery" and action.get("api_payload"):
        httpx.post(f"{MOCK_API_BASE}/mock/instacart/cart", json=action["api_payload"])
    db.update_action(action_id, {
        "completed": 1,
        "completion_date": datetime.utcnow().isoformat(),
        "reviewed": 1,
        "outcome": "Executed on caregiver approval"
    })
```

### 8.4 Caregivers Router

```
GET /caregivers                     — all caregivers with today's availability
GET /caregivers/{id}                — single caregiver + schedule + assignments + tasks
GET /caregivers/{id}/schedule       — 14-day grid (?start_date=&end_date=)
GET /caregivers/{id}/assignments    — patients assigned to this caregiver
```

**`GET /caregivers` response item:**
```json
{
  "caregiver_id": "cg_001", "name": "Sarah Okafor",
  "email": "sarah@sunrisecare.org", "phone": "+1-555-1001",
  "role": "caregiver",
  "today_available": true, "today_booked": false,
  "today_shift": "08:00–16:00",
  "assigned_patient_count": 3,
  "pending_scheduling_task_count": 1
}
```

**`GET /caregivers/{id}/schedule` response:**
```json
{
  "caregiver_id": "cg_001", "name": "Sarah Okafor",
  "schedule": [
    { "date": "2026-04-24", "day_label": "Thu Apr 24",
      "available": true, "booked": false,
      "start_time": "08:00", "end_time": "16:00",
      "slot_state": "free", "booked_task": null },
    { "date": "2026-04-25", "day_label": "Fri Apr 25",
      "available": true, "booked": true,
      "start_time": "08:00", "end_time": "16:00",
      "slot_state": "booked",
      "booked_task": { "action_id": "act_007",
                       "description": "Transport: Margaret → UCSF",
                       "patient_name": "Margaret Chen" } },
    { "date": "2026-04-26", "day_label": "Sat Apr 26",
      "available": false, "booked": false,
      "slot_state": "unavailable", "booked_task": null }
  ]
}
```

`slot_state` values: `"free"` | `"booked"` | `"unavailable"`

### 8.5 Scheduling Router

```
GET  /scheduling/tasks                 — all pending scheduling_task actions
POST /scheduling/{id}/assign           — assign caregiver, book slot, → unconfirmed
POST /scheduling/{id}/confirm          — → confirmed
POST /scheduling/{id}/decline          — free slot, reset → pending_approval, escalate
```

**`GET /scheduling/tasks` response item:**
```json
{
  "action_id": "act_007", "patient_id": "pt_001", "patient_name": "Margaret Chen",
  "manual_action_type": "transport",
  "description": "Transport: Margaret → UCSF Cardiology — Apr 28 10:00am",
  "draft_content": "{\"distance\": \"4.2 miles\", \"duration\": \"22 min\", ...}",
  "urgency_level": "tier_1", "is_overdue": false,
  "review_by": "2026-04-26T10:00:00Z",
  "scheduling_status": "pending_approval",
  "assigned_caregiver": null, "assigned_caregiver_name": null
}
```

**`POST /scheduling/{id}/assign` body:** `{ "caregiver_id": str, "date": str }`
Books slot, sets `scheduling_status="unconfirmed"`, writes notification.
Returns: `{ "status": "assigned", "caregiver_name": "Sarah Okafor" }`

**`POST /scheduling/{id}/decline`**
Calls `db.free_caregiver_slot()`, resets `scheduling_status="pending_approval"`,
clears `assigned_caregiver`, writes escalation notification.
Returns: `{ "status": "escalated" }`

### 8.6 Notifications Router

```
GET  /notifications         — unread notifications, created_at DESC
POST /notifications/{id}/read  — mark read
```

**`GET /notifications` response item:**
```json
{
  "id": 42, "type": "modification_complete",
  "action_id": "act_001", "patient_id": "pt_001",
  "title": "Draft updated",
  "body": "Margaret Chen · Health · Added urgency language",
  "read": false, "created_at": "2026-04-23T10:34:00Z"
}
```

### 8.7 Ingest Router

**`POST /ingest/text`**
Body: `{ "content": str, "caregiver_id": str }`
LLM extraction → `write_patient()` → trigger detection via
`POST http://localhost:8001/internal/detect` with `trigger="patient_create"`.
```json
Response: {
  "patient_id": "pt_004", "name": "Edna Wallace",
  "extracted_fields": ["name", "age", "medications", "appointments"],
  "immediate_flags": ["Digoxin refill due in 2 days", "Cardiology 7 months overdue"]
}
```

LLM extraction prompt:
```python
system = build_system_prompt(
    """Extract patient care data from this caregiver message.
Return JSON only matching this schema:
{ patient_id, name, age, address, medications: [...], appointments: [...],
  grocery: {...}, emergency_contacts: [...] }
Generate patient_id as "pt_" + 3 random digits if not provided.
Use null for any missing fields. Do not invent data.""",
    org_context=db.get_org_profile(), domain="health"
)
```

**`POST /ingest/file`**
Multipart form. PDF → pdfplumber text extraction. Image → Claude vision.
Same extraction system prompt. Same response shape as `/ingest/text`.
Triggers detection after write with `trigger="patient_create"`.

### 8.8 Org Router

```
GET /org      — returns org_profile row
PUT /org      — partial update to org_profile
```

### 8.9 Resend Email Integration (`agents/shared/email.py`)

```python
import httpx, os

RESEND_API_KEY = os.environ["RESEND_API_KEY"]
FROM_EMAIL = "macos@careops.dev"

def send_resend_email(to: str, subject: str, body: str) -> dict:
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                 "Content-Type": "application/json"},
        json={"from": FROM_EMAIL, "to": to, "subject": subject, "text": body}
    )
    return response.json()

# Note: use a personal verified email address for demo.
# Resend free tier: 100 emails/day, instant API key.

SUBJECT_MAP = {
    ("health", "pharmacy"):    "Medication Refill Request — {patient}",
    ("health", "prescriber"):  "URGENT: Clinical Escalation — {patient}",
    ("health", "fda"):         "URGENT: FDA Drug Safety Review — {patient}",
    ("appointment", "clinic"): "Appointment Scheduling Request — {patient}",
}

def build_subject(action: dict) -> str:
    key = (action["domain"], action.get("recipient_type", ""))
    template = SUBJECT_MAP.get(key, "Care Action — {patient}")
    return template.format(patient=action.get("patient_name", "Patient"))
```

---

## 9. REACT DASHBOARD — FOUR VIEWS

### 9.0 App Shell, Routing, NavTabs

**Four routes:**
- `/actions` (default) → `ActionFeedPage`
- `/patients` → `PatientRosterPage`
- `/caregivers` → `CaregiverPage`
- `/org` → `OrgDashboardPage`

**`TopBar.tsx`:**
```
┌──────────────────────────────────────────────────────────────────┐
│ 🏥 Sunrise Care Org        ⏰ 1 overdue        🔴 9 pending      │
│ [Action Feed]  [Patients]  [Caregivers]  [Organisation]          │
└──────────────────────────────────────────────────────────────────┘
```

`AppShell.tsx` renders TopBar + NavTabs + Toast stack (top-right, z-50) + view outlet.
App loads directly to Action Feed — no onboarding gate (org is pre-seeded).
Overdue badge in TopBar is always visible regardless of active view.
Badge counts driven by `useActions()` hook mounted at App level.

---

### 9.1 VIEW 1 — Action Feed (`ActionFeedPage.tsx`)

**Layout:**
```
┌──────────────────────────────────────────────────────────────┐
│ TopBar + NavTabs                                             │
├──────────────────────────────────────────────────────────────┤
│ ⏰ OVERDUE BANNER (amber) — if any overdue actions           │
│ ⚠️  CRITICAL BANNER (red) — if any tier_0 actions           │
├────────────────┬─────────────────────────────────────────────┤
│ PATIENTS       │ PENDING ACTIONS                    TOTAL: 9 │
│ (compact)      │                                             │
│                │ [🔴 OVERDUE ActionCard]                     │
│ 🔴 Margaret   │ [TIER 0 ActionCard]                         │
│  3 · ⏰1      │ [TIER 1 ActionCard]                         │
│                │   └─ [ActionChatPanel if expanded]          │
│ 🔴 Robert     │ [TIER 1 scheduling ActionCard]              │
│  4 actions    │ [TIER 2 ActionCard]                         │
│                │ ...                                          │
│ 🟡 Dorothy    │                                             │
│  2 actions    │                                             │
│                │                                             │
│ + Add Patient  │                                             │
└────────────────┴─────────────────────────────────────────────┘
```

**Hooks:** `useActions()` (15s), `usePatients()` (30s), `useNotifications()` (10s)

Left column: compact patient list. Name, urgency dot, pending count, ⏰ if overdue.
Click → navigate to `/patients` with that patient pre-selected.

**`ActionCard.tsx` — all 7 states:**

**State 1: automated_task (normal)**
```
┌─────────────────────────────────────────────────────────┐
│ [DOMAIN DOT] TIER 2 · HEALTH · Margaret Chen            │
│ Lisinopril refill 7 days overdue                        │
│ Review by: Apr 25 9:00am                               │
│ [View Draft ↓]  [✓ Approve & Send]  [✕ Dismiss]        │
│ [💬 Ask / Modify]   ← health domain only               │
└─────────────────────────────────────────────────────────┘
```

**State 2: manual_approval (normal)**
```
┌─────────────────────────────────────────────────────────┐
│ [DOT] TIER 1 · HEALTH · Robert Harris                   │
│ FDA interaction flag: Warfarin + Aspirin                │
│ Review by: Apr 24 11:00am                              │
│ [View Full Draft ↓]  [✓ Approve & Send]  [✕ Dismiss]   │
│ [💬 Ask / Modify]   ← health domain only               │
└─────────────────────────────────────────────────────────┘
```

Non-health domain action cards (appointment, grocery, financial) show:
`[💬 Ask a Question]` instead of `[💬 Ask / Modify]`.

**State 3: scheduling_task — pending_approval**
```
┌─────────────────────────────────────────────────────────┐
│ [DOT] TIER 1 · SCHEDULING · Margaret Chen               │
│ Transport needed: UCSF Cardiology — Tue Apr 28 10:00am  │
│ Departure 8:45am · 4.2 miles · 22 min                  │
│ Status: PENDING ASSIGNMENT                             │
│ [👤 Go to Scheduling →]  [✕ Dismiss]                   │
└─────────────────────────────────────────────────────────┘
```
"Go to Scheduling →" navigates to `/caregivers` with router state:
`navigate('/caregivers', { state: { selectedActionId: action.action_id } })`

**State 4: scheduling_task — unconfirmed**
```
┌─────────────────────────────────────────────────────────┐
│ [DOT] TIER 1 · SCHEDULING · Margaret Chen               │
│ Transport: UCSF Cardiology — Apr 28 10:00am            │
│ Assigned to: Sarah Okafor  [pulsing yellow dot]        │
│ Status: AWAITING CONFIRMATION                          │
│ [✓ Confirm]  [✕ Decline]  [👤 Reassign →]             │
└─────────────────────────────────────────────────────────┘
```

**State 5: scheduling_task — confirmed**
```
│ Status: CONFIRMED ✓ Sarah Okafor                       │
│ [✓ Mark Complete]                                      │
```

**State 6: scheduling_task — unresolved**
```
┌─────────────────────────────────────────────────────────┐
│ 🔴 OVERDUE · SCHEDULING · Margaret Chen                 │
│ Transport: UCSF Cardiology — UNRESOLVED                 │
│ [👤 Re-assign Caregiver →]  [✕ Dismiss]                │
└─────────────────────────────────────────────────────────┘
```

**State 7: any type — overdue**
Red left border. `⏰ OVERDUE` badge. `is_overdue` timestamp shown.
Approve button replaced with `[⏳ Overdue — Act Now]`.
Always sorted to top of feed via `OVERDUE_SCORE_BOOST`.

**`ActionChatPanel.tsx`**

Slides open below card content. Health cards: "Ask / Modify" toggle.
Non-health cards: "Ask a Question" toggle. Scheduling cards: no chat button.

```
├─────────────────────────────────────────────────────────┤
│ 💬 ASK OR MODIFY THIS ACTION                            │
│                                                         │
│  agent  Updating draft — this will take a moment...    │
│  user   Make it more urgent, mention the risk           │
│  agent  Done. Added urgency language. Draft updated.   │
│                                                         │
│  ┌─────────────────────────────────────┐ [Send ↵]      │
│  │ Ask a question or request a change… │               │
│  └─────────────────────────────────────┘               │
```

Implementation:
- Uses `useActionChat(action.action_id)` — 3s poll while panel is open
- User messages right-aligned (blue), agent messages left-aligned (grey)
- `modification_in_progress=true`: spinner on draft area, Approve disabled
  with tooltip "Draft is being updated…"
- `draft_version` increment: flash draft area green briefly
- Enter key or Send button submits. Optimistic local state append on send.
- Placeholder: `"Ask a question or request a change…"` (health) or
  `"Ask a question about this action…"` (non-health)

**`DraftModal.tsx`**

Slides in from right when "View Draft" clicked.
Shows full `draft_content`. Edit toggle for inline textarea editing.
Top-right: `✏️ v{draft_version}` badge. If `draft_version > 1`: "Modified" chip.
Footer: `[✓ Approve & Send]  [✕ Cancel]`
On approve: calls `api.approveAction()`, closes modal, shows toast "Executed ✓".

**`Banner.tsx`**

Two types, stackable below NavTabs:
- Red: `⚠️ CRITICAL: {description} — {patient_name}  [View] [✕]`
- Amber: `⏰ OVERDUE: {count} action(s) past deadline  [View Overdue] [✕]`
"View Overdue" scrolls action feed to first overdue card.

**`Toast.tsx`**

Top-right corner, z-50. Auto-dismiss after 6 seconds or manual close.
Stack vertically for multiple. Click scrolls to relevant action card.
On dismiss: `api.markNotificationRead(id)`.
- `modification_complete`: teal left border
- `overdue`: red left border
- `scheduling_update`: purple left border

---

### 9.2 VIEW 2 — Patient Roster (`PatientRosterPage.tsx`)

**Layout:**
```
┌──────────────────────────────────────────────────────────────┐
│ TopBar + NavTabs                                             │
├──────────────────────────────────────────────────────────────┤
│ ⏰ / ⚠️  Banners (if applicable)                            │
├────────────────┬─────────────────────────────────────────────┤
│ PATIENTS       │  Margaret Chen  ·  74  ·  San Francisco    │
│                │  Caregivers: Sarah Okafor, James Reyes      │
│ 🔴 Margaret   │  [+ Add Patient]  [✏️ Update Patient]       │
│  3 · ⏰1      │                                             │
│                │  ▼ Medications                             │
│ 🔴 Robert     │    Lisinopril 10mg · Daily                  │
│  4 actions    │    Refill due: Apr 17 ⚠️                   │
│                │    Adherence: ████░░ (4 day gap)           │
│ 🟡 Dorothy    │                                             │
│  2 actions    │  ▼ Appointments                            │
│                │    Cardiology — Dr. Patel                  │
│ + Add Patient  │    Last visit: Aug 2025 ⚠️ 8mo overdue    │
│                │                                             │
│                │  ▼ Grocery                                 │
│                │    Last delivery: Apr 12 ⚠️ 12 days ago   │
│                │                                             │
│                │  ▼ Financial                               │
│                │    PG&E $94 due Apr 27 ⚠️ autopay OFF     │
│                │                                             │
│                │  ── ACTION HISTORY ─────────────────────── │
│                │  [ActionHistoryTable]                       │
│                │                                             │
│                │  ── UPDATE HISTORY ─────────────────────── │
│                │  [UpdateHistoryTable]                       │
└────────────────┴─────────────────────────────────────────────┘
```

**Hooks:** `usePatients()` (30s), `usePatient(selectedId)` (30s when selected)

**`PatientCard` row:**
```
🔴  Margaret Chen · 74          3 pending  ⏰1
```
Color: 🔴 tier_0/tier_1 · 🟡 tier_2 · 🟢 tier_3 or no actions.

**Domain accordion panels** (MedicationPanel, AppointmentPanel, GroceryPanel, FinancialPanel):
- Read-only display of Life Graph data for that domain
- Inline ⚠️ next to any field with a pending action in that domain
- Clicking ⚠️ navigates to `/actions` filtered to that domain + patient

**`ActionHistoryTable` columns:**
```
Date | Domain | Type | Description | Urgency | Status | Outcome | Caregiver
```
Type chip: `AUTO` (blue) · `APPROVAL` (purple) · `SCHEDULING` (violet).
Rows with `is_overdue=1`: amber left border.
Default sort: newest first. Filterable by domain via tab chips.

**Update history section** (below ActionHistoryTable):
```
── UPDATE HISTORY ─────────────────────────────────────────
Date    | Caregiver    | Domain  | Op     | Summary
Apr 23  | Sarah Okafor | Health  | update | Changed Lisinopril dosage to 20mg
Apr 20  | James Reyes  | Grocery | add    | Added low-potassium restriction
```
Driven by `GET /patients/{id}/update-history`.

**`AddPatientPanel.tsx`**

Slides in from right over PatientDetail when "+ Add Patient" clicked.

```
┌─────────────────────────────────────────────────────────┐
│ ← Back          ADD NEW PATIENT                         │
├─────────────────────────────────────────────────────────┤
│ Describe the new patient in plain language. Include:    │
│ name, age, medications, appointments, dietary needs.    │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ e.g. "Adding new patient — Edna Wallace, 79.        │ │
│ │ Takes Digoxin 0.125mg daily, prescribed by Dr.      │ │
│ │ Kim at UCSF. Refill due May 1st..."                 │ │
│ └─────────────────────────────────────────────────────┘ │
│                                          [Add Patient ↵] │
│                                                         │
│ ── After submission ─────────────────────────────────── │
│ ✓ Edna Wallace added.                                   │
│  ⚠️ Digoxin refill due in 2 days                       │
│  ⚠️ Cardiology visit 7 months overdue                  │
│ 2 actions created.              [View Actions →]        │
└─────────────────────────────────────────────────────────┘
```

On submit: `POST /ingest/text`. Show spinner during LLM extraction (2–4s).
"View Actions →" navigates to `/actions?patient_id={new_id}`.

**`UpdatePatientPanel.tsx`**

Slides in from right over PatientDetail when "Update Patient" clicked.
State machine: `idle` → `submitted` → `confirmed` → `applied`

```
┌─────────────────────────────────────────────────────────┐
│ ← Back       UPDATE PATIENT — Margaret Chen             │
├─────────────────────────────────────────────────────────┤
│ Describe what's changed. Medications, appointments,     │
│ dietary needs, financial info, or new notes.            │
│                                                         │
│ [📎 Attach file]                                        │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ e.g. "Dr. Patel increased Lisinopril to 20mg.       │ │
│ │ New refill due May 15th..."                         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                       [Submit ↵]        │
│                                                         │
│ ── Pending confirmation ─────────────────────────────── │
│ Proposed changes:                                       │
│  • Health / update: Lisinopril dosage → 20mg           │
│    refill_due → 2026-05-15                              │
│ Risk level: LOW                                         │
│ [✓ Confirm Changes]  [✕ Cancel]                        │
│                                                         │
│ ── After confirmation ───────────────────────────────── │
│ ✓ Changes applied. Detection re-running…               │
│  ⚠️ Refill date updated — no immediate action needed   │
│                                      [View Actions →]   │
└─────────────────────────────────────────────────────────┘
```

```typescript
async function handleSubmit(content: string) {
  setState('submitted');
  const pending = await api.submitPatientUpdate(patientId, content, caregiverId);
  setPendingUpdate(pending);
}
async function handleConfirm() {
  const result = await api.confirmPatientUpdate(patientId, pendingUpdate.update_id);
  setState('applied');
  setFlags(result.new_flags);
}
```

File attachment: `📎 Attach file` → file picker → `POST /patients/{id}/update/file`.
Same pending + confirmation flow as text update.

---

### 9.3 VIEW 3 — Caregiver Management (`CaregiverPage.tsx`)

**Layout:**
```
┌──────────────────────────────────────────────────────────────┐
│ TopBar + NavTabs                                             │
├──────────────────────────────────────────────────────────────┤
│ ── PENDING SCHEDULING TASKS ─── [SchedulingPanel strip] ──── │
│  🚗 Transport · Margaret → UCSF · Apr 28  [Assign ↓]        │
│  🛒 Grocery · Dorothy · Overdue 12 days   [Assign ↓]  [...] │
├────────────────┬─────────────────────────────────────────────┤
│ CAREGIVERS     │  Sarah Okafor                               │
│                │  Today: Thu Apr 24  ·  08:00–16:00          │
│ 🟢 Sarah O.   │  ● Available (not booked)                   │
│  3 patients   │                                             │
│                │  ── SCHEDULE (14 days) ──────────────────── │
│ 🟡 James R.   │  [ScheduleGrid]                             │
│  3 patients   │                                             │
│                │  ── PATIENT ASSIGNMENTS ─────────────────── │
│ ⚪ Linda P.   │  [AssignmentList]                           │
│  0 patients   │                                             │
│                │  ── ACTIVE SCHEDULING TASKS ──────────────── │
│ ...           │  Transport · Margaret → UCSF                 │
│                │  UNCONFIRMED  [✓ Confirm]  [✕ Decline]      │
└────────────────┴─────────────────────────────────────────────┘
```

**Hooks:** `useCaregivers()` (60s), `useCaregiver(selectedId)` (30s),
`useCaregiverSchedule(selectedId)` (30s), `useSchedulingTasks()` (15s)

**Deep-link mount logic:**

```typescript
// CaregiverPage.tsx
const location = useLocation();
const preSelectedActionId = location.state?.selectedActionId ?? null;
<SchedulingPanel preSelectedActionId={preSelectedActionId} />
```

**`SchedulingPanel.tsx`**

Horizontal strip, always visible in View 3. Each task is a compact card.
When `preSelectedActionId` is set, auto-expands that task's assignment form
and scrolls to it.

```typescript
useEffect(() => {
  if (preSelectedActionId) {
    setExpandedTaskId(preSelectedActionId);
    document.getElementById(`task-${preSelectedActionId}`)?.scrollIntoView();
  }
}, [preSelectedActionId]);
```

Task card (pending_approval):
```
┌──────────────────────────────────────────────────────────┐
│ 🚗 TRANSPORT · Margaret Chen                             │
│ UCSF Cardiology — Tue Apr 28 10:00am                    │
│ Status: PENDING ASSIGNMENT     Review by: Apr 26 10:00am │
│ [Assign Caregiver ↓]  [✕ Dismiss]                       │
└──────────────────────────────────────────────────────────┘
```

When "Assign Caregiver ↓" clicked, expand inline form:
```
┌──────────────────────────────────────────────────────────┐
│ 🚗 TRANSPORT · Margaret Chen — ASSIGN CAREGIVER          │
│                                                          │
│ ★ Sarah Okafor     Mon Apr 28 · 08:00–16:00  [Select]   │
│   Marcus Webb      Mon Apr 28 · 10:00–18:00  [Select]   │
│   Kevin Huang      Tue Apr 29 · 09:00–17:00  [Select]   │
│                                                          │
│ ★ = assigned to this patient         [Cancel]            │
└──────────────────────────────────────────────────────────┘
```

On Select: `POST /scheduling/{id}/assign { caregiver_id, date }`.
Task card updates to "ASSIGNED → Sarah Okafor — awaiting confirmation".
Left sidebar caregiver dot turns 🟡 (booked). Strip scrolls to next task.
Overdue tasks shown with red border + ⏰ badge.

**`CaregiverCard.tsx` row:**
```
🟢  Sarah Okafor            3 patients  08:00–16:00
```
🟢 = available + not booked · 🟡 = booked today · ⚪ = not working.
Sorted: available today first, then by assigned patient count.

**`CaregiverDetail.tsx`**

**Header:**
```
Sarah Okafor
Today: Thursday Apr 24  ·  08:00–16:00  ·  ● Available (not booked)
Email: sarah@sunrisecare.org  ·  Phone: +1-555-1001
```

**`ScheduleGrid.tsx`** — 14-day grid, one column per day:
```
        Thu    Fri    Sat    Sun    Mon    Tue    ...
        Apr24  Apr25  Apr26  Apr27  Apr28  Apr29
        ─────  ─────  ─────  ─────  ─────  ─────
       │ FREE │BOOKD │ OFF  │ OFF  │ FREE │ FREE │
       │08-16 │08-16 │      │      │08-16 │08-16 │
       │      │Marg. │      │      │      │      │
        ─────  ─────  ─────  ─────  ─────  ─────
```
`free` = green · `booked` = amber · `unavailable` = grey.
Clicking a booked slot shows tooltip with task description.
Today's column has blue left border.

**`AssignmentList.tsx`:**
```
Margaret Chen  ·  74  ·  tier_2  ·  3 pending  [View Patient →]
Robert Harris  ·  81  ·  tier_1  ·  4 pending  [View Patient →]
Dorothy Kim    ·  68  ·  tier_2  ·  2 pending  [View Patient →]
```
"View Patient →" navigates to `/patients` with patient pre-selected.

**Active Scheduling Tasks section:**
```
🚗 Transport · Margaret Chen → UCSF Cardiology
   Tue Apr 28 10:00am  ·  UNCONFIRMED  ·  Awaiting confirmation
   [✓ Confirm]  [✕ Decline]

🛒 Grocery · Dorothy Kim
   Status: CONFIRMED ✓  ·  Apr 29
   [✓ Mark Complete]
```

---

### 9.4 VIEW 4 — Organisation Dashboard (`OrgDashboardPage.tsx`)

**Layout:**
```
┌──────────────────────────────────────────────────────────────┐
│ TopBar + NavTabs                                             │
├──────────────────────────────────────────────────────────────┤
│                                                             │
│  SUNRISE CARE ORG                                           │
│  Nonprofit home care · San Francisco, CA                    │
│  12 patients · 10 caregivers · 1:3 ratio                    │
│  Escalation lead: Admin — Dr. Priya Nair                    │
│                                                             │
│  ── CARE PROTOCOLS ──────────────────────────────────────── │
│  ▼ Health Protocol                                          │
│    Flag any missed medication dose streak ≥ 3 days.        │
│    Always cc prescriber on refill requests.                 │
│    [This protocol is injected into all Health Agent prompts]│
│                                                             │
│  ▶ Transport Protocol                                       │
│  ▶ Financial Protocol                                       │
│                                                             │
│  ── CAREGIVER ROSTER ────────────────────────────────────── │
│  Name           Role       Today         Patients  Tasks   │
│  Sarah Okafor   caregiver  08:00–16:00   3         1       │
│  James Reyes    caregiver  09:00–17:00   3         0       │
│  Linda Park     caregiver  OFF           0         0       │
│  ...                                                        │
│                                                             │
│  ── ORG METRICS ─────────────────────────────────────────── │
│  [9 Pending]  [2 Completed Today]  [1 Overdue]  [2 Sched.] │
│                                                             │
└──────────────────────────────────────────────────────────────┘
```

**Hooks:** `useOrg()` (300s), `useCaregivers()` (60s, reused), `useActions()` (reused)

**`useOrg.ts`:**
```typescript
export function useOrg(): OrgProfile | null {
  const [org, setOrg] = useState<OrgProfile | null>(null);
  useEffect(() => {
    const load = () => api.getOrg().then(setOrg);
    load();
    const id = setInterval(load, 300_000);
    return () => clearInterval(id);
  }, []);
  return org;
}
```

**`OrgSummary.tsx`** — header card: org_name, org_type, location, patient/caregiver
counts, ratio, escalation_lead, care_philosophy. Read-only.

**`ProtocolPanel.tsx`** — one per domain (health, transport, financial).
Accordion. Shows protocol text from org_profile verbatim.
Subtitle: *"This protocol is injected into all {domain} agent prompts."*

**`CaregiverRoster.tsx`** — compact table of all 10 caregivers.
Columns: Name · Role · Today's shift · Patients assigned · Active scheduling tasks.
Each row links to View 3 pre-selecting that caregiver.

**`OrgMetrics.tsx`** — 4 stat cards driven by `useActions()` filtered counts:
```
[Total Pending: 9]  [Completed Today: 2]  [Overdue: 1]  [Pending Scheduling: 2]
```
Simple `<div>` cards — no charting library.

---

## 10. TYPESCRIPT TYPES (`src/types/index.ts`)

```typescript
// ── Shared ────────────────────────────────────────────────────────────────────
export type UrgencyLevel  = 'tier_0' | 'tier_1' | 'tier_2' | 'tier_3';
export type Domain        = 'health' | 'appointment' | 'grocery' | 'financial' | 'scheduling';
export type ActionType    = 'automated_task' | 'manual_approval' | 'scheduling_task';
export type SchedulingStatus = 'pending_approval' | 'unconfirmed' | 'confirmed' | 'unresolved';
export type SlotState     = 'free' | 'booked' | 'unavailable';

// ── View 1: Actions ───────────────────────────────────────────────────────────
export interface Action {
  action_id: string;
  patient_id: string;
  patient_name: string;
  domain: Domain;
  type: ActionType;
  description: string;
  draft_content: string | null;
  draft_version: number;
  modification_in_progress: boolean;
  urgency_level: UrgencyLevel;
  is_overdue: boolean;
  review_by: string;
  scheduling_status: SchedulingStatus | null;
  manual_action_type: string | null;
  assigned_caregiver: string | null;
  assigned_caregiver_name: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  action_id: string;
  role: 'user' | 'agent';
  intent: 'modification' | 'question' | null;
  content: string;
  created_at: string;
}

export interface Notification {
  id: number;
  type: 'modification_complete' | 'overdue' | 'new_action' | 'scheduling_update';
  action_id: string;
  patient_id: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
}

// ── View 2: Patients ──────────────────────────────────────────────────────────
export interface PatientSummary {
  patient_id: string;
  name: string;
  age: number;
  urgency_level: UrgencyLevel;
  pending_action_count: number;
  overdue_action_count: number;
  assigned_caregivers: { caregiver_id: string; name: string }[];
}

export interface Medication {
  med_id: string;
  name: string;
  dosage: string;
  frequency: string;
  prescriber: string;
  prescriber_email: string;
  pharmacy: string;
  pharmacy_email: string;
  last_refill: string;
  days_supply: number;
  refill_due: string;
  adherence_log: string[];
}

export interface Appointment {
  appt_id: string;
  provider: string;
  specialty: string;
  last_visit: string | null;
  next_scheduled: string | null;
  recommended_frequency_months: number;
  clinic_address: string;
  phone: string;
  clinic_email: string;
}

export interface GroceryProfile {
  dietary_restrictions: string[];
  last_delivery: string;
  staples: { item: string; frequency_days: number; last_ordered: string }[];
}

export interface FinancialProfile {
  bills: { name: string; amount: number; due_date: string; autopay: boolean }[];
  anomalies: { description: string; detected_at: string }[];
}

export interface CaregiverNote {
  caregiver_id: string;
  date: string;
  note: string;
}

export interface ActionHistoryItem {
  action_id: string;
  domain: Domain;
  type: ActionType;
  description: string;
  urgency_level: UrgencyLevel;
  is_overdue: boolean;
  reviewed: boolean;
  completed: boolean;
  completion_date: string | null;
  assigned_caregiver: string | null;
  outcome: string | null;
  created_at: string;
}

export interface PatientUpdateRecord {
  id: number;
  patient_id: string;
  caregiver_id: string;
  domain: string;
  operation: 'add' | 'update' | 'remove';
  fields_changed: string[];
  summary: string;
  confirmed: boolean;
  applied: boolean;
  created_at: string;
}

export interface PendingPatientUpdate {
  update_id: number;
  summary: string;
  domain: string;
  operation: string;
  fields_changed: string[];
  proposed_changes: Record<string, unknown>;
  requires_confirmation: true;
}

export interface LifeGraph {
  patient_id: string;
  name: string;
  age: number;
  address: string;
  medications: Medication[];
  appointments: Appointment[];
  grocery: GroceryProfile;
  financial: FinancialProfile;
  caregiver_notes: CaregiverNote[];
  pending_actions: Action[];
  action_history: ActionHistoryItem[];
}

// ── View 3: Caregivers ────────────────────────────────────────────────────────
export interface CaregiverSummary {
  caregiver_id: string;
  name: string;
  email: string;
  today_available: boolean;
  today_booked: boolean;
  today_shift: string | null;
  assigned_patient_count: number;
  pending_scheduling_task_count: number;
}

export interface CaregiverDetail extends CaregiverSummary {
  phone: string;
  role: string;
  assigned_patients: PatientSummary[];
  active_scheduling_tasks: Action[];
}

export interface ScheduleDay {
  date: string;
  day_label: string;
  available: boolean;
  booked: boolean;
  start_time: string | null;
  end_time: string | null;
  slot_state: SlotState;
  booked_task: {
    action_id: string;
    description: string;
    patient_name: string;
  } | null;
}

export interface CaregiverSchedule {
  caregiver_id: string;
  name: string;
  schedule: ScheduleDay[];
}

export interface AvailableCaregiverSlot {
  caregiver_id: string;
  name: string;
  date: string;
  start_time: string;
  end_time: string;
  assigned_to_patient: boolean;
  slot_label: string;
}

// ── View 4: Org ───────────────────────────────────────────────────────────────
export interface OrgProfile {
  id: number;
  org_name: string;
  org_type: string;
  location: string;
  patient_count_approx: number;
  caregiver_count_approx: number;
  care_philosophy: string;
  decision_making_approach: string;
  continuity_preference: string;
  caregiver_patient_ratio: string;
  visit_frequency_default: number;
  escalation_chain: string;
  escalation_lead: string;
  health_protocol: string;
  transport_protocol: string;
  financial_protocol: string;
  created_at: string;
}
```

---

## 11. API CLIENT (`src/api/client.ts`)

```typescript
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = {

  // ── View 1: Actions ────────────────────────────────────────────────────────
  getActions: (filters?: Record<string, string>): Promise<Action[]> => {
    const params = new URLSearchParams(filters);
    return fetch(`${BASE}/actions?${params}`).then(r => r.json());
  },
  approveAction: (id: string) =>
    fetch(`${BASE}/actions/${id}/approve`, { method: 'POST' }).then(r => r.json()),
  dismissAction: (id: string) =>
    fetch(`${BASE}/actions/${id}/dismiss`, { method: 'POST' }).then(r => r.json()),
  sendActionChat: (id: string, content: string, patientId: string) =>
    fetch(`${BASE}/actions/${id}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, patient_id: patientId, caregiver_id: 'cg_001' })
    }).then(r => r.json()),
  getChatHistory: (id: string): Promise<ChatMessage[]> =>
    fetch(`${BASE}/actions/${id}/chat-history`).then(r => r.json()),
  getNotifications: (): Promise<Notification[]> =>
    fetch(`${BASE}/notifications`).then(r => r.json()),
  markNotificationRead: (id: number) =>
    fetch(`${BASE}/notifications/${id}/read`, { method: 'POST' }).then(r => r.json()),

  // ── View 2: Patients ───────────────────────────────────────────────────────
  getPatients: (): Promise<PatientSummary[]> =>
    fetch(`${BASE}/patients`).then(r => r.json()),
  getPatient: (id: string): Promise<LifeGraph> =>
    fetch(`${BASE}/patients/${id}`).then(r => r.json()),
  ingestText: (content: string, caregiverId: string) =>
    fetch(`${BASE}/ingest/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, caregiver_id: caregiverId })
    }).then(r => r.json()),
  submitPatientUpdate: (patientId: string, content: string,
                        caregiverId: string): Promise<PendingPatientUpdate> =>
    fetch(`${BASE}/patients/${patientId}/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, caregiver_id: caregiverId })
    }).then(r => r.json()),
  confirmPatientUpdate: (patientId: string, updateId: number) =>
    fetch(`${BASE}/patients/${patientId}/update/${updateId}/confirm`,
      { method: 'POST' }).then(r => r.json()),
  getPatientUpdateHistory: (patientId: string): Promise<PatientUpdateRecord[]> =>
    fetch(`${BASE}/patients/${patientId}/update-history`).then(r => r.json()),

  // ── View 3: Caregivers ─────────────────────────────────────────────────────
  getCaregivers: (): Promise<CaregiverSummary[]> =>
    fetch(`${BASE}/caregivers`).then(r => r.json()),
  getCaregiver: (id: string): Promise<CaregiverDetail> =>
    fetch(`${BASE}/caregivers/${id}`).then(r => r.json()),
  getCaregiverSchedule: (id: string, startDate: string,
                          endDate: string): Promise<CaregiverSchedule> =>
    fetch(`${BASE}/caregivers/${id}/schedule?start_date=${startDate}&end_date=${endDate}`)
      .then(r => r.json()),
  getSchedulingTasks: (): Promise<Action[]> =>
    fetch(`${BASE}/scheduling/tasks`).then(r => r.json()),
  getAvailableCaregivers: (date: string, manualActionType: string,
                            patientId: string): Promise<AvailableCaregiverSlot[]> =>
    fetch(`${BASE}/mock/caregivers/available`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, manual_action_type: manualActionType,
                             patient_id: patientId, duration_hours: 2.0 })
    }).then(r => r.json()).then(d => d.available_caregivers),
  assignScheduling: (actionId: string, caregiverId: string, date: string) =>
    fetch(`${BASE}/scheduling/${actionId}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caregiver_id: caregiverId, date })
    }).then(r => r.json()),
  confirmScheduling: (actionId: string) =>
    fetch(`${BASE}/scheduling/${actionId}/confirm`,
      { method: 'POST' }).then(r => r.json()),
  declineScheduling: (actionId: string) =>
    fetch(`${BASE}/scheduling/${actionId}/decline`,
      { method: 'POST' }).then(r => r.json()),

  // ── View 4: Org ────────────────────────────────────────────────────────────
  getOrg: (): Promise<OrgProfile> =>
    fetch(`${BASE}/org`).then(r => r.json()),
  updateOrg: (updates: Partial<OrgProfile>) =>
    fetch(`${BASE}/org`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    }).then(r => r.json()),
};
```

---

## 12. HOOKS (`src/hooks/`)

```typescript
// ── View 1 ─────────────────────────────────────────────────────────────────

// useActions.ts — 15s poll
export function useActions(filters?: Record<string, string>): Action[] {
  const [actions, setActions] = useState<Action[]>([]);
  useEffect(() => {
    const load = () => api.getActions(filters).then(setActions);
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, [JSON.stringify(filters)]);
  return actions;
}

// useActionChat.ts — 3s poll (only when panel is open)
export function useActionChat(actionId: string | null): ChatMessage[] {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  useEffect(() => {
    if (!actionId) { setMessages([]); return; }
    const load = () => api.getChatHistory(actionId).then(setMessages);
    load();
    const id = setInterval(load, 3_000);
    return () => clearInterval(id);
  }, [actionId]);
  return messages;
}

// useNotifications.ts — 10s poll
export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  useEffect(() => {
    const load = () => api.getNotifications().then(setNotifications);
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);
  return { notifications, markRead: api.markNotificationRead };
}

// ── View 2 ─────────────────────────────────────────────────────────────────

// usePatients.ts — 30s poll
export function usePatients(): PatientSummary[] {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  useEffect(() => {
    const load = () => api.getPatients().then(setPatients);
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);
  return patients;
}

// usePatient.ts — 30s poll (only active when patient selected)
export function usePatient(patientId: string | null): LifeGraph | null {
  const [patient, setPatient] = useState<LifeGraph | null>(null);
  useEffect(() => {
    if (!patientId) { setPatient(null); return; }
    const load = () => api.getPatient(patientId).then(setPatient);
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [patientId]);
  return patient;
}

// ── View 3 ─────────────────────────────────────────────────────────────────

// useCaregivers.ts — 60s poll
export function useCaregivers(): CaregiverSummary[] {
  const [caregivers, setCaregivers] = useState<CaregiverSummary[]>([]);
  useEffect(() => {
    const load = () => api.getCaregivers().then(setCaregivers);
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, []);
  return caregivers;
}

// useCaregiver.ts — 30s poll
export function useCaregiver(caregiverId: string | null): CaregiverDetail | null {
  const [caregiver, setCaregiver] = useState<CaregiverDetail | null>(null);
  useEffect(() => {
    if (!caregiverId) { setCaregiver(null); return; }
    const load = () => api.getCaregiver(caregiverId).then(setCaregiver);
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [caregiverId]);
  return caregiver;
}

// useCaregiverSchedule.ts — 30s poll
export function useCaregiverSchedule(
  caregiverId: string | null,
  startDate: string,
  endDate: string
): CaregiverSchedule | null {
  const [schedule, setSchedule] = useState<CaregiverSchedule | null>(null);
  useEffect(() => {
    if (!caregiverId) { setSchedule(null); return; }
    const load = () =>
      api.getCaregiverSchedule(caregiverId, startDate, endDate).then(setSchedule);
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [caregiverId, startDate, endDate]);
  return schedule;
}

// useSchedulingTasks.ts — 15s poll
export function useSchedulingTasks(): Action[] {
  const [tasks, setTasks] = useState<Action[]>([]);
  useEffect(() => {
    const load = () => api.getSchedulingTasks().then(setTasks);
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, []);
  return tasks;
}

// ── View 4 ─────────────────────────────────────────────────────────────────

// useOrg.ts — 300s poll (org data is stable)
export function useOrg(): OrgProfile | null {
  const [org, setOrg] = useState<OrgProfile | null>(null);
  useEffect(() => {
    const load = () => api.getOrg().then(setOrg);
    load();
    const id = setInterval(load, 300_000);
    return () => clearInterval(id);
  }, []);
  return org;
}
```

---

## 13. ENVIRONMENT VARIABLES (`.env.example`)

```
# Agent framework
AGENTVERSE_API_KEY=

# Agent addresses (set after Agentverse registration)
EXECUTOR_AGENT_ADDRESS=
HEALTH_SUPERVISOR_ADDRESS=
APPT_SUPERVISOR_ADDRESS=
GROCERY_SUPERVISOR_ADDRESS=
FINANCIAL_SUPERVISOR_ADDRESS=
SCHEDULING_AGENT_ADDRESS=

# LLM
ANTHROPIC_API_KEY=

# Email (use a personal verified address for demo)
RESEND_API_KEY=

# Real APIs
GOOGLE_MAPS_API_KEY=
# OpenFDA: no key required

# Internal Executor endpoint (FastAPI → Executor detection trigger)
EXECUTOR_INTERNAL_URL=http://localhost:8001

# Mock API base URL (for agents calling mock endpoints)
MOCK_API_BASE=http://localhost:8000

# Dashboard
VITE_API_URL=http://localhost:8000

# Database
SQLITE_DB_PATH=data/life_graph.db
```

---

## 14. `requirements.txt`

```
uagents>=0.12.0
fastapi>=0.110.0
uvicorn>=0.29.0
anthropic>=0.25.0
httpx>=0.27.0
pdfplumber>=0.11.0
python-multipart>=0.0.9
python-dotenv>=1.0.0
pydantic>=2.6.0
```

---

## 15. BUILD ORDER & SPRINT CHECKLIST

### Sprint 1 — Foundation (Hours 0–1)
- [ ] Full directory structure
- [ ] `schema.sql` — all tables including `org_profile`, `patient_updates`,
      `action_chat`, `notifications`, `expiration_notifications`
- [ ] Initialize SQLite, run schema
- [ ] `db.py` — all helpers including org, patient update, soft delete,
      chat, notification, caregiver, scheduling
- [ ] `models.py` — all models including `OnDemandDetectionRequest`
- [ ] `constants.py` — all constants including `ORG_CONTEXT_MAP`,
      `MODIFICATION_ENABLED_DOMAINS`, `DETECTION_TRIGGERS`, `OVERDUE_SCORE_BOOST`
- [ ] `llm.py` — `call_claude`, `call_claude_json`, `call_claude_vision`,
      `build_system_prompt()`
- [ ] `seed.py` — org_profile + 3 patients + 10 caregivers + 14-day schedule
      rows + 1 pre-seeded overdue action
- [ ] Verify: `SELECT * FROM org_profile` returns 1 row;
      `SELECT COUNT(*) FROM caregiver_schedule` returns 140 (10 × 14)
- [ ] Register all 10 agents on Agentverse, copy addresses to `.env`
- [ ] Scaffold `run_all.py`
- [ ] Scaffold Vite + React + Tailwind + React Router (4 routes)

### Sprint 2 — Mock APIs + Ingestion (Hours 1–3)
- [ ] CVS, Cal, Instacart, Amazon mock FastAPI routers
- [ ] `/mock/caregivers/available` — reads live SQLite, assigns-to-patient sorted first
- [ ] `ingest.py` — text (LLM extraction) + file (vision + pdfplumber)
      Both trigger `POST /internal/detect` after write
- [ ] `org.py` router — GET + PUT
- [ ] Executor internal HTTP server on port 8001 (`/internal/detect` endpoint)
- [ ] `email.py` Resend wrapper + `build_subject()`
- [ ] Test: `POST /ingest/text` → patient written → internal detect endpoint called
- [ ] Test: `GET /org` returns seeded data

### Sprint 3 — Health Domain (Hours 3–5)
- [ ] Health Supervisor: `on_message(OnDemandDetectionRequest)` — no `@on_interval`
- [ ] Health Supervisor: org context injection via `build_system_prompt()`
- [ ] Health Supervisor: risk scoring LLM pass, `review_by` calc, `db.write_action()`
- [ ] Health Supervisor: Modification handlers A + B
- [ ] Health Supervisor: Q&A handlers C + D
- [ ] Health Worker: all 4 detection checks (refill, missed dose, OpenFDA interaction,
      OpenFDA recall)
- [ ] Health Worker: modification task handler with `fetch_live_data()`
- [ ] Health Worker: Q&A task handler
- [ ] Wire: `/internal/detect` → `run_detection()` → Health Supervisor → Worker
      → Supervisor → Executor → `action_history`
- [ ] Test: call `/internal/detect` with `pt_001` → Lisinopril refill action written
- [ ] Test: call with `pt_002` → OpenFDA Warfarin+Aspirin action written
- [ ] Test: org health_protocol text appears in generated draft email
- [ ] Test: submit modification → revised draft returned → `draft_version` = 2
- [ ] Test: submit Q&A → concise answer written to `action_chat`

### Sprint 4 — Remaining Domains (Hours 5–7)
- [ ] Appointment Supervisor + Worker: detection (overdue appt, Google Maps transport,
      visit prep) + Q&A handlers
- [ ] Grocery Supervisor + Worker: detection (staleness, dietary conflict, supply) + Q&A
- [ ] Financial Supervisor + Worker: detection (bill due, autopay miss, anomaly) + Q&A
- [ ] All non-health supervisors: no modification handlers
- [ ] Scheduling tasks all propagate with `scheduling_status="pending_approval"`
- [ ] Test: call `/internal/detect` with all 3 patients → all 9 seeded issues generate actions
- [ ] Test: non-health Q&A returns answer inline; modification attempt returns
      "not supported yet" message

### Sprint 5 — Executor + Update Patient + FastAPI (Hours 7–8.5)
- [ ] Executor: expiration loop (`@on_interval(900)`) with overdue check,
      ASI:One null guard, dashboard notification, deduplication
- [ ] Executor: `run_detection()` function
- [ ] Executor: `classify_intent()` with keyword pre-check + LLM fallback
- [ ] Executor: `handle_modification()`, `handle_question()`,
      `handle_onboarding()`, `handle_scheduling_query()`, `handle_general_query()`
- [ ] Executor: `on_modification_result()`, `on_question_answer()`,
      `on_supervisor_result()`, `on_chat()`
- [ ] FastAPI: all routers wired in `main.py`
- [ ] FastAPI: `POST /patients/{id}/update` — LLM classify + pending write
- [ ] FastAPI: `POST /patients/{id}/update/{uid}/confirm` — apply + detect
- [ ] FastAPI: `POST /patients/{id}/update/file`
- [ ] FastAPI: `GET /patients/{id}/update-history`
- [ ] Test: `GET /actions` returns seeded overdue action at top (score boost)
- [ ] Test: submit patient update → pending returned → confirm → `active=0`
      for removal → detection fires → new action in `action_history`
- [ ] Test: expiration loop detects seeded overdue action (already `is_overdue=1`)
      and does NOT double-notify (deduplication check)

### Sprint 6 — Scheduling Agent (Hours 8.5–9)
- [ ] Scheduling Agent: `on_message(SchedulingQuery)` — query mock API, format list,
      store options, send to ASI:One
- [ ] Scheduling Agent: `on_message(ChatMessage)` — parse number reply, update action
      to `unconfirmed`, book slot, write notification
- [ ] Test: ASI:One scheduling query → options list returned → selection → action
      shows `unconfirmed` in dashboard

### Sprint 7 — Dashboard View 1: Action Feed (Hours 9–9.5)
- [ ] `AppShell`, `TopBar`, `NavTabs` — 4 tabs, overdue badge
- [ ] `ActionFeedPage` — split layout
- [ ] `ActionFeed` + all 7 `ActionCard` states
- [ ] Health cards: "Ask / Modify" button; non-health: "Ask a Question"; scheduling: none
- [ ] Scheduling card: `navigate('/caregivers', { state: { selectedActionId } })`
- [ ] `ActionChatPanel` with `useActionChat` 3s poll, placeholder varies by domain
- [ ] `DraftModal` with `draft_version` badge + "Modified" chip when > 1
- [ ] `modification_in_progress`: spinner on draft, disabled Approve
- [ ] `draft_version` increment: green flash on draft area
- [ ] `Banner` (overdue amber + tier_0 red) + `Toast` stack
- [ ] Test: health card → modify → in-progress state → draft updates → toast fires
- [ ] Test: non-health card → Q&A → inline answer, no toast
- [ ] Test: overdue seeded action at top with red border on page load

### Sprint 8 — Dashboard View 2: Patient Roster (Hours 9.5–10.25)
- [ ] `PatientRosterPage` split layout
- [ ] `PatientSidebar` + `PatientCard` rows with urgency + overdue
- [ ] `PatientDetail` header with "Update Patient" button
- [ ] `MedicationPanel`, `AppointmentPanel`, `GroceryPanel`, `FinancialPanel`
      with ⚠️ indicators linking to Action Feed
- [ ] `ActionHistoryTable` — domain filter tabs, overdue row highlight
- [ ] Update history section — `GET /patients/{id}/update-history`
- [ ] `AddPatientPanel` — free-text, LLM extract, flags, "View Actions →"
- [ ] `UpdatePatientPanel` — state machine idle→submitted→confirmed→applied,
      file attachment, proposed changes display, confirm button
- [ ] Test: update patient → proposed changes shown → confirm → Life Graph updated
      → detection fires → new flag shown → "View Actions →" navigates correctly

### Sprint 9 — Dashboard View 3: Caregiver Management (Hours 10.25–10.75)
- [ ] `CaregiverPage` layout with scheduling strip + split layout
- [ ] `SchedulingPanel` — task cards, inline assignment form, caregiver list,
      pre-selected from router state, auto-scroll
- [ ] `CaregiverSidebar` + `CaregiverCard` rows with availability dots
- [ ] `CaregiverDetail` — header, `ScheduleGrid`, `AssignmentList`,
      active scheduling tasks with confirm/decline
- [ ] `ScheduleGrid` — 14-day grid, slot states, today highlight, booked tooltips
- [ ] `AssignmentList` — patient rows with "View Patient →" links
- [ ] Test: deep-link from View 1 → View 3 pre-selects and auto-expands correct task
- [ ] Test: assign caregiver → slot turns booked → sidebar dot turns 🟡

### Sprint 10 — Dashboard View 4: Org Dashboard (Hours 10.75–11.25)
- [ ] `OrgDashboardPage` layout
- [ ] `OrgSummary` — header from seeded org_profile
- [ ] `ProtocolPanel` — 3 domain accordions with protocol text + "injected into agents" note
- [ ] `CaregiverRoster` — 10-row table linking to View 3
- [ ] `OrgMetrics` — 4 stat cards
- [ ] `useOrg` hook (300s poll)
- [ ] Test: `GET /org` returns seeded data → all panels populated

### Sprint 11 — E2E Polish + Submission (Hours 11.25–12)
- [ ] Full demo scenario across all 4 views (see Section 16)
- [ ] Verify org protocol text appears in generated draft emails
- [ ] Verify soft delete: remove medication → `active=0` → gone from Life Graph
- [ ] Verify detection on update: change medication → new action generated
- [ ] Verify health modify + non-health Q&A distinction is clear in UI
- [ ] Verify scheduling deep-link pre-selects correct task
- [ ] Verify overdue seeded action is first in feed on load
- [ ] Tune all LLM prompts for clinical tone
- [ ] README: architecture diagram, 4-view walkthrough, env setup, demo script
- [ ] Push to public GitHub
- [ ] Record 5-minute demo video
- [ ] Devpost submission with all Agentverse agent addresses

---

## 16. DEMO SCENARIO GUIDE (5 minutes, live)

**Minute 1 — Action Feed (View 1)**
Open app. Seeded overdue action (Dorothy, Metformin escalation) at top with red border —
visible immediately without waiting. Show 9 total actions ranked by urgency.
Note health card shows "Ask / Modify"; appointment card shows "Ask a Question" only.
Narrate: "Health is the only domain with modification in v1 — others support Q&A."

**Minute 2 — Modify + Q&A**
Click Margaret's refill card. Open DraftModal (v1).
Tap "Ask / Modify". Type: "Add that she's been non-adherent 4 days — make it more urgent."
Card enters in-progress — Approve greys out. ~5 seconds later: toast fires top-right
"Draft updated · Health · Added urgency language." Draft flashes green.
Open DraftModal — v2 badge. Note org protocol language in draft ("cc prescriber").
Approve — Resend fires.
Then: click Robert's FDA interaction card. "Ask a Question":
"What are the actual risks of Warfarin + Aspirin together?"
Inline answer within 3 seconds. No toast — it's conversational, not a state change.

**Minute 3 — Patient Roster (View 2)**
Switch to Patients. Click Margaret. Show Life Graph accordions — ⚠️ on refill date.
Click ⚠️ → navigates back to Action Feed filtered to Margaret's health actions.
Return to Patients. Click "Update Patient". Type:
"Dr. Patel increased her Lisinopril to 20mg, new refill due May 15th."
Proposed changes panel: "Health / update: dosage → 20mg, refill_due → 2026-05-15."
Click Confirm. "Detection re-running…" → "Refill date updated — no immediate action."
Update history row appears at bottom.

**Minute 4 — Caregiver Management (View 3) via deep-link**
Back to Action Feed. Click "Go to Scheduling →" on Margaret's transport card.
View 3 opens — SchedulingPanel pre-scrolled to Margaret's task, form auto-expanded.
Show 3 available caregivers, Sarah Okafor starred (assigned to patient).
Select Sarah. Card → "ASSIGNED → Sarah Okafor — awaiting confirmation."
Sarah's sidebar dot turns 🟡.
Click Sarah in sidebar — ScheduleGrid shows Apr 28 slot as BOOKED (amber).
In Active Scheduling Tasks section: Confirm. Status → CONFIRMED ✓.

**Minute 5 — Organisation Dashboard (View 4)**
Switch to Organisation tab. Show org summary — care philosophy, escalation lead.
Open Health Protocol accordion. Read protocol text.
"This exact text is injected into every Health Agent LLM prompt — that's why
the draft email said 'cc prescriber' without us asking."
Show CaregiverRoster — Sarah now shows 1 active task.
Show OrgMetrics — action counts updated in real time.

---

## 17. PIPELINE SUMMARY TABLE

| Capability | Trigger | Hops | Worker? | State change | Notification |
|---|---|---|---|---|---|
| Detection | patient_create or patient_update | Exec→Sup→Work→Sup→Exec | Always | New actions in action_history | Action Feed reorder |
| Modification | Health action card chat | Exec→Sup→[Work]→Sup→Exec | Only if live API | Draft replaced, version++ | Global toast |
| Q&A | Any action card chat | Exec→Sup→[Work]→Sup→Exec | Only if live API | None | Inline only |
| Patient update | UpdatePatientPanel confirm | FastAPI→DB→/internal/detect | No | Life Graph tables updated | Detection re-runs |
| Scheduling assign | View 3 SchedulingPanel | FastAPI→DB | No | pending→unconfirmed | Slot booked, toast |
| Scheduling confirm | View 3 task card | FastAPI→DB | No | unconfirmed→confirmed | Card update |
| Expiration (15-min) | Executor @on_interval | Internal | No | is_overdue=1, tier_0 | Dashboard notification + ASI:One (if address set) |

---

## 18. FUTURE WORK (for Devpost submission)

- Modification pipeline for Appointment, Grocery, and Financial domain action cards
- Org onboarding wizard (conversational, fullscreen) for new org setup from scratch
- Multi-org support with org-level authentication
- Caregiver mobile app (ASI:One currently serves as the caregiver-facing interface)
- Real Cal.com, Instacart, and Amazon API integrations replacing mock endpoints
- Patient risk scoring across domains (cross-domain correlation, e.g. medication
  non-adherence + worsening notes + overdue appointment = elevated composite risk)

---

*End of MACOS Build Spec v7 Final*
