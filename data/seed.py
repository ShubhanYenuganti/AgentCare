"""Seed deterministic Sprint 2 data into SQLite (normalized schema)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path("data/life_graph.db")
SCHEMA_PATH = Path("data/schema.sql")

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

PATIENTS = [
    {
        "patient_id": "pt_001",
        "name": "Margaret Chen",
        "age": 74,
        "address": "123 Sunset Blvd, San Francisco, CA 94122",
        "preferences": {"appointment_times": ["morning"], "transport_preference": "family_first"},
    },
    {
        "patient_id": "pt_002",
        "name": "Robert Harris",
        "age": 81,
        "address": "88 Ocean Ave, San Francisco, CA 94112",
        "preferences": {"appointment_times": ["morning"], "transport_preference": "caregiver"},
    },
    {
        "patient_id": "pt_003",
        "name": "Dorothy Kim",
        "age": 68,
        "address": "45 Noriega St, San Francisco, CA 94122",
        "preferences": {"appointment_times": ["afternoon"], "transport_preference": "family_first"},
    },
]

EMERGENCY_CONTACTS = [
    {"patient_id": "pt_001", "name": "Linda Chen",  "relation": "daughter", "phone": "+1-555-0192"},
    {"patient_id": "pt_002", "name": "Tom Harris",  "relation": "son",      "phone": "+1-555-0234"},
    {"patient_id": "pt_003", "name": "Grace Kim",   "relation": "niece",    "phone": "+1-555-0388"},
]

MEDICATIONS = [
    {
        "med_id": "med_001",
        "patient_id": "pt_001",
        "name": "Lisinopril",
        "dosage": "10mg",
        "frequency": "once daily",
        "prescriber": "Dr. Anita Patel",
        "prescriber_email": "dr.patel@ucsf-cardiology.com",
        "pharmacy": "CVS Mission St",
        "pharmacy_email": "cvs.missionst@cvs.com",
        "last_refill": "2026-03-18",
        "days_supply": 30,
        "refill_due": "2026-04-17",
        "adherence_log": [
            "2026-04-23", "2026-04-22", "2026-04-21",
            "2026-04-20", "2026-04-19",
        ],
    },
    {
        "med_id": "med_002",
        "patient_id": "pt_002",
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
            "2026-04-20", "2026-04-19", "2026-04-18",
        ],
    },
    {
        "med_id": "med_003",
        "patient_id": "pt_002",
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
            "2026-04-20", "2026-04-19", "2026-04-18",
        ],
    },
    {
        "med_id": "med_004",
        "patient_id": "pt_003",
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
            "2026-04-19", "2026-04-18", "2026-04-17",
            "2026-04-16", "2026-04-15",
        ],
    },
]

CAREGIVER_NOTES = [
    {
        "patient_id": "pt_001",
        "caregiver_id": "cg_001",
        "date": "2026-04-21",
        "note": "Margaret seemed tired today, resting most of the afternoon.",
    },
    {
        "patient_id": "pt_002",
        "caregiver_id": "cg_002",
        "date": "2026-04-22",
        "note": "Robert in good spirits, walked to the garden independently.",
    },
    {
        "patient_id": "pt_003",
        "caregiver_id": "cg_001",
        "date": "2026-04-22",
        "note": "Dorothy reported increased fatigue and dizziness. She declined lunch and spent most of the day in bed.",
    },
    {
        "patient_id": "pt_003",
        "caregiver_id": "cg_002",
        "date": "2026-04-21",
        "note": "Dorothy seemed withdrawn today, less talkative than usual.",
    },
]

APPOINTMENTS = [
    {
        "appt_id": "appt_001",
        "patient_id": "pt_001",
        "provider": "Dr. Anita Patel",
        "specialty": "Cardiology",
        "last_visit": "2025-08-10",
        "next_scheduled": None,
        "recommended_frequency_months": 6,
        "clinic_address": "400 Parnassus Ave, SF CA 94143",
        "phone": "+1-555-0144",
        "clinic_email": "cardiology@ucsf.edu",
    },
    {
        "appt_id": "appt_002",
        "patient_id": "pt_002",
        "provider": "Dr. Maya Torres",
        "specialty": "Physical Therapy",
        "last_visit": "2026-01-03",
        "next_scheduled": None,
        "recommended_frequency_months": 3,
        "clinic_address": "1001 Potrero Ave, SF CA 94110",
        "phone": "+1-555-0311",
        "clinic_email": "physio@sfgeneral.org",
    },
    {
        "appt_id": "appt_003",
        "patient_id": "pt_003",
        "provider": "Dr. Carlos Reyes",
        "specialty": "Endocrinology",
        "last_visit": "2026-01-15",
        "next_scheduled": None,
        "recommended_frequency_months": 3,
        "clinic_address": "2340 Sutter St, SF CA 94115",
        "phone": "+1-555-0421",
        "clinic_email": "appointments@sfdiabetesclinic.com",
    },
]

GROCERY = [
    {
        "patient_id": "pt_001",
        "dietary_restrictions": ["low sodium", "diabetic-friendly"],
        "last_delivery": "2026-04-12",
        "staples": [
            {"item": "spinach",        "frequency_days": 7,  "last_ordered": "2026-04-12"},
            {"item": "chicken breast", "frequency_days": 7,  "last_ordered": "2026-04-12"},
            {"item": "brown rice",     "frequency_days": 14, "last_ordered": "2026-04-12"},
            {"item": "greek yogurt",   "frequency_days": 7,  "last_ordered": "2026-04-12"},
        ],
    },
    {
        "patient_id": "pt_002",
        "dietary_restrictions": ["low fat", "heart healthy"],
        "last_delivery": "2026-04-20",
        "staples": [
            {"item": "oatmeal",     "frequency_days": 7, "last_ordered": "2026-04-20"},
            {"item": "salmon",      "frequency_days": 7, "last_ordered": "2026-04-20"},
            {"item": "blueberries", "frequency_days": 7, "last_ordered": "2026-04-20"},
            {"item": "whole milk",  "frequency_days": 7, "last_ordered": "2026-04-20"},
        ],
    },
    {
        "patient_id": "pt_003",
        "dietary_restrictions": ["diabetic-friendly", "low sugar"],
        "last_delivery": "2026-04-18",
        "staples": [
            {"item": "leafy greens",   "frequency_days": 7,  "last_ordered": "2026-04-18"},
            {"item": "eggs",           "frequency_days": 7,  "last_ordered": "2026-04-18"},
            {"item": "almonds",        "frequency_days": 14, "last_ordered": "2026-04-18"},
            {"item": "cottage cheese", "frequency_days": 7,  "last_ordered": "2026-04-18"},
        ],
    },
]

FINANCIAL_BILLS = [
    {"patient_id": "pt_001", "name": "PG&E",           "amount": 94.00,  "due_date": "2026-04-27", "autopay": 0},
    {"patient_id": "pt_001", "name": "Medicare Part B", "amount": 174.70, "due_date": "2026-05-01", "autopay": 1},
    {"patient_id": "pt_002", "name": "Pacific Gas & Electric", "amount": 340.00, "due_date": "2026-04-30", "autopay": 0},
    {"patient_id": "pt_002", "name": "Medicare Part B", "amount": 174.70, "due_date": "2026-05-01", "autopay": 1},
    {"patient_id": "pt_003", "name": "Medicare Part B", "amount": 174.70, "due_date": "2026-04-01", "autopay": 1},
]

FINANCIAL_ANOMALIES = [
    {
        "patient_id": "pt_002",
        "description": "PG&E charge $340 vs prior average $95 — 258% above baseline",
        "detected_at": "2026-04-23",
    },
]

CAREGIVERS = [
    ("cg_001", "Sarah Okafor", "sarah@sunrisecare.org", "+1-555-1001", "caregiver", ["Mon", "Tue", "Wed", "Thu", "Fri"], "08:00", "16:00"),
    ("cg_002", "James Reyes",  "james@sunrisecare.org", "+1-555-1002", "caregiver", ["Mon", "Wed", "Fri"],               "09:00", "17:00"),
    ("cg_003", "Linda Park",   "linda@sunrisecare.org", "+1-555-1003", "caregiver", ["Tue", "Thu", "Sat"],               "07:00", "15:00"),
    ("cg_004", "Marcus Webb",  "marcus@sunrisecare.org", "+1-555-1004", "caregiver", ["Mon", "Tue", "Thu", "Fri"],       "10:00", "18:00"),
    ("cg_005", "Priya Nair",   "priya@sunrisecare.org", "+1-555-1005", "admin",     ["Wed", "Thu", "Fri", "Sat"],        "08:00", "14:00"),
    ("cg_006", "Tom Callahan", "tom@sunrisecare.org",   "+1-555-1006", "caregiver", ["Mon", "Tue", "Wed"],               "12:00", "20:00"),
    ("cg_007", "Aisha Diallo", "aisha@sunrisecare.org", "+1-555-1007", "caregiver", ["Thu", "Fri", "Sat", "Sun"],        "08:00", "16:00"),
    ("cg_008", "Kevin Huang",  "kevin@sunrisecare.org", "+1-555-1008", "caregiver", ["Mon", "Wed", "Fri", "Sun"],        "09:00", "17:00"),
    ("cg_009", "Rosa Medina",  "rosa@sunrisecare.org",  "+1-555-1009", "caregiver", ["Tue", "Wed", "Thu"],               "07:00", "15:00"),
    ("cg_010", "Daniel Frost", "daniel@sunrisecare.org", "+1-555-1010", "caregiver", ["Mon", "Tue", "Wed", "Thu", "Fri"], "14:00", "22:00"),
]

PATIENT_CAREGIVER_ASSIGNMENTS = [
    ("pt_001", "cg_001"),
    ("pt_001", "cg_002"),
    ("pt_002", "cg_001"),
    ("pt_002", "cg_002"),
    ("pt_003", "cg_001"),
    ("pt_003", "cg_002"),
]

SEEDED_ACTIONS = [
    # ── Health: Metformin missed 4 days (tier_0, urgent) ──────────────────────
    {
        "action_id": "act_seed_001",
        "patient_id": "pt_003",
        "domain": "health",
        "type": "manual_approval",
        "description": "Metformin missed 4 days — condition worsening, caregiver escalation pending",
        "draft_content": (
            "Dear Dr. Reyes, Dorothy Kim (68) missed her Metformin 500mg for 4 consecutive "
            "days. Caregiver notes from Apr 22 report increased fatigue and dizziness. "
            "Requesting immediate review and guidance on next steps."
        ),
        "urgency_level": "tier_0",
        "is_overdue": 0,
        "review_by": "2026-04-28T09:00:00Z",
        "invocation_date": "2026-04-23T07:00:00Z",
        "escalation_count": 1,
        "scheduling_status": None,
        "manual_action_type": None,
    },
    # ── Appointment: Margaret Chen cardiology visit due (tier_1) ──────────────
    {
        "action_id": "act_seed_002",
        "patient_id": "pt_001",
        "domain": "appointment",
        "type": "manual_approval",
        "description": "Cardiology follow-up due — last visit Aug 2025, 8 months since last check",
        "draft_content": (
            "Dear Dr. Patel, Margaret Chen (74) is due for her 6-month cardiology follow-up. "
            "Her last visit was August 10, 2025 — it has now been 8 months. "
            "Please advise on availability for an appointment in late April or May 2026."
        ),
        "urgency_level": "tier_1",
        "is_overdue": 0,
        "review_by": "2026-04-30T17:00:00Z",
        "invocation_date": "2026-04-24T08:00:00Z",
        "escalation_count": 0,
        "scheduling_status": None,
        "manual_action_type": None,
    },
    # ── Appointment: Robert Harris PT scheduling needed (tier_1) ──────────────
    {
        "action_id": "act_seed_003",
        "patient_id": "pt_002",
        "domain": "appointment",
        "type": "scheduling",
        "description": "Physical therapy appointment — caregiver transport needed Apr 28",
        "draft_content": (
            "Robert Harris (81) has a physical therapy appointment scheduled for Apr 28 at "
            "SFGH (1001 Potrero Ave). He requires caregiver transport — 48h advance notice required. "
            "Please assign an available caregiver for morning transport."
        ),
        "urgency_level": "tier_1",
        "is_overdue": 0,
        "review_by": "2026-04-26T12:00:00Z",
        "invocation_date": "2026-04-24T09:00:00Z",
        "escalation_count": 0,
        "scheduling_status": "pending_approval",
        "manual_action_type": "transport",
        "caregiver_options_json": '[{"caregiver_id":"cg_004","name":"Marcus Webb","available":true},{"caregiver_id":"cg_006","name":"Tom Callahan","available":true},{"caregiver_id":"cg_008","name":"Kevin Huang","available":true}]',
        "schedule": {"date": "2026-04-28", "start_time": "10:00", "end_time": "12:00"},
    },
    # ── Financial: PG&E anomaly for Robert Harris (tier_1) ────────────────────
    {
        "action_id": "act_seed_004",
        "patient_id": "pt_002",
        "domain": "financial",
        "type": "manual_approval",
        "description": "PG&E bill $340 — 258% above baseline $95, review before payment",
        "draft_content": (
            "Robert Harris received a PG&E bill of $340 due Apr 30, compared to his prior "
            "average of $95. This is 258% above baseline and requires admin review before "
            "any payment action is taken per org financial protocol."
        ),
        "urgency_level": "tier_1",
        "is_overdue": 0,
        "review_by": "2026-04-29T17:00:00Z",
        "invocation_date": "2026-04-24T08:30:00Z",
        "escalation_count": 0,
        "scheduling_status": None,
        "manual_action_type": None,
    },
    # ── Grocery: Margaret Chen staples reorder needed (tier_2) ───────────────
    {
        "action_id": "act_seed_005",
        "patient_id": "pt_001",
        "domain": "grocery",
        "type": "manual_approval",
        "description": "Weekly grocery staples — last delivery Apr 12, reorder needed this week",
        "draft_content": (
            "Margaret Chen's weekly grocery staples are due for reorder. Last delivery was Apr 12 "
            "(12 days ago). Items needed: spinach, chicken breast, greek yogurt (all 7-day "
            "frequency). Brown rice (14-day) is also due. Please approve reorder for "
            "delivery this week."
        ),
        "urgency_level": "tier_2",
        "is_overdue": 0,
        "review_by": "2026-04-29T12:00:00Z",
        "invocation_date": "2026-04-24T10:00:00Z",
        "escalation_count": 0,
        "scheduling_status": None,
        "manual_action_type": None,
    },
    # ── Appointment: Dorothy Kim endocrinology — caregiver assigned, unconfirmed ──
    {
        "action_id": "act_seed_006",
        "patient_id": "pt_003",
        "domain": "appointment",
        "type": "scheduling",
        "description": "Endocrinology follow-up Apr 30 — transport assigned, awaiting confirmation",
        "draft_content": (
            "Dorothy Kim (68) has an endocrinology appointment Apr 30 with Dr. Carlos Reyes "
            "(2340 Sutter St). Family transport preferred but unavailable — Sarah Okafor (cg_001) "
            "has been assigned. Awaiting caregiver confirmation."
        ),
        "urgency_level": "tier_1",
        "is_overdue": 0,
        "review_by": "2026-04-28T12:00:00Z",
        "invocation_date": "2026-04-24T09:30:00Z",
        "escalation_count": 0,
        "scheduling_status": "unconfirmed",
        "manual_action_type": "transport",
        "assigned_caregiver": "cg_001",
    },
]

DAY_MAP = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
SEED_DATE = date(2026, 4, 24)


def _reset_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM expiration_notifications;
        DELETE FROM notifications;
        DELETE FROM action_chat;
        DELETE FROM action_history;
        DELETE FROM patient_caregivers;
        DELETE FROM caregiver_schedule;
        DELETE FROM caregivers;
        DELETE FROM patient_updates;
        DELETE FROM financial_anomalies;
        DELETE FROM financial_bills;
        DELETE FROM grocery_staples;
        DELETE FROM grocery;
        DELETE FROM appointments;
        DELETE FROM caregiver_notes;
        DELETE FROM medications;
        DELETE FROM emergency_contacts;
        DELETE FROM patients;
        DELETE FROM org_profile;
        """
    )


def _seed_org(conn: sqlite3.Connection) -> None:
    columns = ", ".join(ORG_PROFILE.keys())
    placeholders = ", ".join(["?"] * len(ORG_PROFILE))
    conn.execute(
        f"INSERT INTO org_profile ({columns}) VALUES ({placeholders})",
        list(ORG_PROFILE.values()),
    )


def _seed_patients(conn: sqlite3.Connection) -> None:
    for patient in PATIENTS:
        conn.execute(
            """
            INSERT INTO patients (patient_id, name, age, address, preferences_json, active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                patient["patient_id"],
                patient["name"],
                patient["age"],
                patient["address"],
                json.dumps(patient["preferences"]),
            ),
        )


def _seed_emergency_contacts(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO emergency_contacts (patient_id, name, relation, phone, active)
        VALUES (:patient_id, :name, :relation, :phone, 1)
        """,
        EMERGENCY_CONTACTS,
    )


def _seed_medications(conn: sqlite3.Connection) -> None:
    for med in MEDICATIONS:
        conn.execute(
            """
            INSERT INTO medications (
                med_id, patient_id, name, dosage, frequency, prescriber, prescriber_email,
                pharmacy, pharmacy_email, last_refill, days_supply, refill_due,
                adherence_log_json, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                med["med_id"],
                med["patient_id"],
                med["name"],
                med["dosage"],
                med["frequency"],
                med["prescriber"],
                med["prescriber_email"],
                med["pharmacy"],
                med["pharmacy_email"],
                med["last_refill"],
                med["days_supply"],
                med["refill_due"],
                json.dumps(med["adherence_log"]),
            ),
        )


def _seed_caregiver_notes(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO caregiver_notes (patient_id, caregiver_id, date, note, active)
        VALUES (:patient_id, :caregiver_id, :date, :note, 1)
        """,
        CAREGIVER_NOTES,
    )


def _seed_appointments(conn: sqlite3.Connection) -> None:
    for appt in APPOINTMENTS:
        conn.execute(
            """
            INSERT INTO appointments (
                appt_id, patient_id, provider, specialty, last_visit, next_scheduled,
                recommended_frequency_months, clinic_address, phone, clinic_email, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                appt["appt_id"],
                appt["patient_id"],
                appt["provider"],
                appt["specialty"],
                appt["last_visit"],
                appt["next_scheduled"],
                appt["recommended_frequency_months"],
                appt["clinic_address"],
                appt["phone"],
                appt["clinic_email"],
            ),
        )


def _seed_grocery(conn: sqlite3.Connection) -> None:
    for g in GROCERY:
        conn.execute(
            """
            INSERT INTO grocery (patient_id, dietary_restrictions_json, last_delivery)
            VALUES (?, ?, ?)
            """,
            (g["patient_id"], json.dumps(g["dietary_restrictions"]), g["last_delivery"]),
        )
        for staple in g["staples"]:
            conn.execute(
                """
                INSERT INTO grocery_staples (patient_id, item, frequency_days, last_ordered, active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (g["patient_id"], staple["item"], staple["frequency_days"], staple["last_ordered"]),
            )


def _seed_financial(conn: sqlite3.Connection) -> None:
    for bill in FINANCIAL_BILLS:
        conn.execute(
            """
            INSERT INTO financial_bills (patient_id, name, amount, due_date, autopay, active)
            VALUES (:patient_id, :name, :amount, :due_date, :autopay, 1)
            """,
            bill,
        )
    for anomaly in FINANCIAL_ANOMALIES:
        conn.execute(
            """
            INSERT INTO financial_anomalies (patient_id, description, detected_at)
            VALUES (:patient_id, :description, :detected_at)
            """,
            anomaly,
        )


def _seed_caregivers_and_schedule(conn: sqlite3.Connection) -> None:
    for caregiver_id, name, email, phone, role, days, start, end in CAREGIVERS:
        conn.execute(
            """
            INSERT INTO caregivers (caregiver_id, name, email, phone, asi_one_address, role)
            VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (caregiver_id, name, email, phone, role),
        )
        working_days = {DAY_MAP[d] for d in days}
        for i in range(14):
            target = SEED_DATE + timedelta(days=i)
            working = target.weekday() in working_days
            conn.execute(
                """
                INSERT INTO caregiver_schedule (caregiver_id, date, start_time, end_time, available, booked)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    caregiver_id,
                    target.isoformat(),
                    start if working else None,
                    end if working else None,
                    1 if working else 0,
                ),
            )


def _seed_assignments(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO patient_caregivers (patient_id, caregiver_id) VALUES (?, ?)",
        PATIENT_CAREGIVER_ASSIGNMENTS,
    )


def _seed_actions(conn: sqlite3.Connection) -> None:
    for action in SEEDED_ACTIONS:
        raw_schedule = action.get("schedule")
        conn.execute(
            """
            INSERT INTO action_history (
                action_id, patient_id, domain, type, description, draft_content, urgency_level,
                review_by, invocation_date, is_overdue, escalation_count, scheduling_status,
                manual_action_type, reviewed, completed, completion_date, assigned_caregiver,
                caregiver_options_json, outcome, draft_version, modification_in_progress, schedule
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, ?, ?, NULL, 1, 0, ?)
            """,
            (
                action["action_id"],
                action["patient_id"],
                action["domain"],
                action["type"],
                action["description"],
                action["draft_content"],
                action["urgency_level"],
                action["review_by"],
                action["invocation_date"],
                action["is_overdue"],
                action["escalation_count"],
                action.get("scheduling_status"),
                action.get("manual_action_type"),
                action.get("assigned_caregiver"),
                action.get("caregiver_options_json"),
                json.dumps(raw_schedule) if raw_schedule is not None else None,
            ),
        )


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _seed_org(connection)
        _seed_patients(connection)
        _seed_emergency_contacts(connection)
        _seed_medications(connection)
        _seed_caregiver_notes(connection)
        _seed_appointments(connection)
        _seed_grocery(connection)
        _seed_financial(connection)
        _seed_caregivers_and_schedule(connection)
        _seed_assignments(connection)
        _seed_actions(connection)
        connection.commit()


if __name__ == "__main__":
    main()
