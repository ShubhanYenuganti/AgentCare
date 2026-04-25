"""Seed deterministic Sprint 1 data into SQLite."""

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
    "care_philosophy": "Person-centred care prioritising autonomy and dignity.",
    "decision_making_approach": "Conservative escalation-first approach.",
    "continuity_preference": "Assign same caregivers to patients where possible.",
    "caregiver_patient_ratio": "1:3 maximum",
    "visit_frequency_default": 7,
    "escalation_chain": "Caregiver -> Org Admin -> Emergency Contact",
    "escalation_lead": "Admin - Dr. Priya Nair",
    "health_protocol": "Flag missed medication streak >= 3 days.",
    "transport_protocol": "Family transport preferred where possible.",
    "financial_protocol": "No payment actions without caregiver sign-off.",
}

PATIENTS = [
    {
        "patient_id": "pt_001",
        "name": "Margaret Chen",
        "age": 74,
        "address": "123 Sunset Blvd, San Francisco, CA 94122",
        "pharmacy_name": "CVS Mission St",
        "pharmacy_email": "pharmacy@cvs-mission.example",
        "doctor_name": "Dr. Anita Patel",
        "doctor_email": "dr.anita.patel@exampleclinic.org",
        "preferences": {"appointment_times": ["morning"], "transport_preference": "family_first"},
        "medications": [{"name": "Lisinopril", "refill_due": "2026-04-17"}],
    },
    {
        "patient_id": "pt_002",
        "name": "Robert Harris",
        "age": 81,
        "address": "88 Ocean Ave, San Francisco, CA 94112",
        "pharmacy_name": "CVS Mission St",
        "pharmacy_email": "pharmacy@cvs-mission.example",
        "doctor_name": "Dr. Ravi Singh",
        "doctor_email": "dr.ravi.singh@exampleclinic.org",
        "preferences": {"appointment_times": ["morning"], "transport_preference": "caregiver"},
        "medications": [{"name": "Warfarin"}, {"name": "Aspirin"}],
    },
    {
        "patient_id": "pt_003",
        "name": "Dorothy Kim",
        "age": 68,
        "address": "45 Noriega St, San Francisco, CA 94122",
        "pharmacy_name": "CVS Mission St",
        "pharmacy_email": "pharmacy@cvs-mission.example",
        "doctor_name": "NP Monica Tran",
        "doctor_email": "np.monica.tran@exampleclinic.org",
        "preferences": {"appointment_times": ["afternoon"], "transport_preference": "family_first"},
        "medications": [{"name": "Metformin", "last_dose": "2026-04-19"}],
    },
]

CAREGIVERS = [
    ("cg_001", "Sarah Okafor", "sarah@sunrisecare.org", "+1-555-1001", "caregiver", ["Mon", "Tue", "Wed", "Thu", "Fri"], "08:00", "16:00"),
    ("cg_002", "James Reyes", "james@sunrisecare.org", "+1-555-1002", "caregiver", ["Mon", "Wed", "Fri"], "09:00", "17:00"),
    ("cg_003", "Linda Park", "linda@sunrisecare.org", "+1-555-1003", "caregiver", ["Tue", "Thu", "Sat"], "07:00", "15:00"),
    ("cg_004", "Marcus Webb", "marcus@sunrisecare.org", "+1-555-1004", "caregiver", ["Mon", "Tue", "Thu", "Fri"], "10:00", "18:00"),
    ("cg_005", "Priya Nair", "priya@sunrisecare.org", "+1-555-1005", "admin", ["Wed", "Thu", "Fri", "Sat"], "08:00", "14:00"),
    ("cg_006", "Tom Callahan", "tom@sunrisecare.org", "+1-555-1006", "caregiver", ["Mon", "Tue", "Wed"], "12:00", "20:00"),
    ("cg_007", "Aisha Diallo", "aisha@sunrisecare.org", "+1-555-1007", "caregiver", ["Thu", "Fri", "Sat", "Sun"], "08:00", "16:00"),
    ("cg_008", "Kevin Huang", "kevin@sunrisecare.org", "+1-555-1008", "caregiver", ["Mon", "Wed", "Fri", "Sun"], "09:00", "17:00"),
    ("cg_009", "Rosa Medina", "rosa@sunrisecare.org", "+1-555-1009", "caregiver", ["Tue", "Wed", "Thu"], "07:00", "15:00"),
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

SEEDED_OVERDUE_ACTION = {
    "action_id": "act_seed_overdue_001",
    "patient_id": "pt_003",
    "domain": "health",
    "type": "manual_approval",
    "description": "Metformin missed 4 days - condition worsening escalation",
    "draft_content": "Dear Dr. Reyes, Dorothy Kim missed Metformin for 4 days.",
    "urgency_level": "tier_0",
    "is_overdue": 1,
    "review_by": "2026-04-23T09:00:00Z",
    "invocation_date": "2026-04-23T07:00:00Z",
    "escalation_count": 1,
    "reviewed": 0,
    "completed": 0,
}

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
            INSERT INTO patients (
                patient_id, name, age, address,
                pharmacy_name, pharmacy_email, doctor_name, doctor_email,
                preferences_json, life_graph_json, active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                patient["patient_id"],
                patient["name"],
                patient["age"],
                patient["address"],
                patient["pharmacy_name"],
                patient["pharmacy_email"],
                patient["doctor_name"],
                patient["doctor_email"],
                json.dumps(patient["preferences"]),
                json.dumps(patient),
            ),
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
        working_days = {DAY_MAP[item] for item in days}
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
        """
        INSERT INTO patient_caregivers (patient_id, caregiver_id)
        VALUES (?, ?)
        """,
        PATIENT_CAREGIVER_ASSIGNMENTS,
    )


def _seed_overdue_action(conn: sqlite3.Connection) -> None:
    action = SEEDED_OVERDUE_ACTION
    conn.execute(
        """
        INSERT INTO action_history (
            action_id, patient_id, domain, type, description, draft_content, urgency_level,
            review_by, invocation_date, is_overdue, escalation_count, reviewed, completed,
            draft_version, modification_in_progress
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
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
            action["reviewed"],
            action["completed"],
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
        _seed_caregivers_and_schedule(connection)
        _seed_assignments(connection)
        _seed_overdue_action(connection)
        connection.commit()


if __name__ == "__main__":
    main()
