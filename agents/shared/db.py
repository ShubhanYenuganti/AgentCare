"""SQLite read/write helpers for MACOS Sprint 1."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from agents.shared.constants import DOMAIN_PRIORITY, OVERDUE_SCORE_BOOST, URGENCY_SCORES

DB_PATH_ENV = "SQLITE_DB_PATH"
DEFAULT_DB_PATH = "data/life_graph.db"
SCHEMA_PATH = "data/schema.sql"


def _db_path() -> Path:
    return Path(os.getenv(DB_PATH_ENV, DEFAULT_DB_PATH))


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("ALTER TABLE patient_updates ADD COLUMN proposed_changes TEXT")
        connection.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    return connection


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return dict(row) if row else {}


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _json_load(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def init_db(schema_path: str = SCHEMA_PATH) -> None:
    schema = Path(schema_path).read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema)
        try:
            conn.execute("ALTER TABLE action_history ADD COLUMN schedule TEXT")
        except Exception:
            pass  # column already exists
        conn.commit()


# Org helpers
def get_setup_status() -> dict[str, Any]:
    with get_connection() as conn:
        org = conn.execute("SELECT org_name FROM org_profile LIMIT 1").fetchone()
        cg_count = conn.execute("SELECT COUNT(*) as n FROM caregivers").fetchone()["n"]
        pt_count = conn.execute("SELECT COUNT(*) as n FROM patients").fetchone()["n"]
    return {
        "org_configured": bool(org and org["org_name"]),
        "caregiver_count": cg_count,
        "patient_count": pt_count,
    }


def get_org_profile() -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM org_profile ORDER BY id ASC LIMIT 1"
        ).fetchone()
        return _row_to_dict(row)


def update_org_profile(updates: dict[str, Any]) -> None:
    if not updates:
        return
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM org_profile ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if not existing:
            columns = ", ".join(updates.keys())
            placeholders = ", ".join(["?"] * len(updates))
            conn.execute(
                f"INSERT INTO org_profile ({columns}) VALUES ({placeholders})",
                list(updates.values()),
            )
            conn.commit()
            return
        set_clause = ", ".join([f"{key}=?" for key in updates.keys()])
        conn.execute(
            f"UPDATE org_profile SET {set_clause} WHERE id=?",
            [*updates.values(), existing["id"]],
        )
        conn.commit()


# Patient helpers
def get_all_patients() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM patients WHERE active=1 ORDER BY created_at DESC"
        ).fetchall()
    results = _rows_to_dicts(rows)
    for row in results:
        row["preferences_json"] = _json_load(row.get("preferences_json"), {})
    return results


def _normalize_person_name(name: str) -> str:
    return " ".join((name or "").strip().split()).lower()


def _name_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", _normalize_person_name(text))


def _name_token_matches(name_token: str, query_token: str) -> bool:
    if not query_token:
        return False
    if name_token == query_token:
        return True
    return len(query_token) >= 3 and name_token.startswith(query_token)


def find_active_patients_by_name(name: str) -> list[dict[str, Any]]:
    """Return active patients whose name exactly matches (case/space-insensitive)."""
    target = _normalize_person_name(name)
    if not target:
        return []
    matches: list[dict[str, Any]] = []
    for patient in get_all_patients():
        if _normalize_person_name(str(patient.get("name", ""))) == target:
            matches.append(patient)
    return matches


def find_active_patients_by_name_query(query: str) -> list[dict[str, Any]]:
    """
    Return active patients whose names are referenced in free text.

    Matching rules:
    - exact full-name phrase match, or
    - partial token match (query token is a prefix of a patient name token)
    """
    normalized_query = _normalize_person_name(query)
    if not normalized_query:
        return []

    query_tokens = _name_tokens(normalized_query)
    if not query_tokens:
        return []

    matches: list[dict[str, Any]] = []
    for patient in get_all_patients():
        name = _normalize_person_name(str(patient.get("name", "")))
        if not name:
            continue

        full_name_match = re.search(rf"(?<!\w){re.escape(name)}(?!\w)", normalized_query) is not None
        name_tokens = _name_tokens(name)
        partial_match = any(
            _name_token_matches(name_token, query_token)
            for name_token in name_tokens
            for query_token in query_tokens
        )

        if full_name_match or partial_match:
            matches.append(patient)
    return matches


def get_patient(patient_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE patient_id=? LIMIT 1", (patient_id,)
        ).fetchone()
    result = _row_to_dict(row)
    if result:
        result["preferences_json"] = _json_load(result.get("preferences_json"), {})
    return result


def write_patient(data: dict[str, Any]) -> str:
    patient_id = data.get("patient_id") or f"pt_{uuid4().hex[:8]}"
    # Use None when preferences not explicitly provided so COALESCE preserves existing value
    raw_prefs = data["preferences"] if "preferences" in data else data.get("preferences_json")
    prefs_value = json.dumps(raw_prefs) if isinstance(raw_prefs, (dict, list)) else raw_prefs
    name_val = data.get("name")
    age_val = data.get("age")
    addr_val = data.get("address")
    active_val = data.get("active", 1)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO patients (patient_id, name, age, address, preferences_json, active)
            VALUES (?, COALESCE(?, 'Unknown Patient'), ?, ?, ?, COALESCE(?, 1))
            ON CONFLICT(patient_id) DO UPDATE SET
                name=COALESCE(?, name),
                age=COALESCE(?, age),
                address=COALESCE(?, address),
                preferences_json=COALESCE(?, preferences_json),
                active=excluded.active
            """,
            (
                patient_id, name_val, age_val, addr_val, prefs_value, active_val,
                # ON CONFLICT binds — raw values so NULL means "don't overwrite"
                name_val, age_val, addr_val, prefs_value,
            ),
        )

        for med in data.get("medications", []):
            med_id = med.get("med_id") or f"med_{uuid4().hex[:8]}"
            adherence = med.get("adherence_log", med.get("adherence_log_json"))
            conn.execute(
                """
                INSERT INTO medications (
                    med_id, patient_id, name, dosage, frequency, prescriber,
                    prescriber_email, pharmacy, pharmacy_email, last_refill,
                    days_supply, refill_due, adherence_log_json, active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, 1))
                ON CONFLICT(med_id) DO UPDATE SET
                    patient_id=excluded.patient_id, name=excluded.name,
                    dosage=excluded.dosage, frequency=excluded.frequency,
                    prescriber=excluded.prescriber, prescriber_email=excluded.prescriber_email,
                    pharmacy=excluded.pharmacy, pharmacy_email=excluded.pharmacy_email,
                    last_refill=excluded.last_refill, days_supply=excluded.days_supply,
                    refill_due=excluded.refill_due,
                    adherence_log_json=excluded.adherence_log_json, active=excluded.active
                """,
                (
                    med_id, patient_id, med.get("name"), med.get("dosage"), med.get("frequency"),
                    med.get("prescriber"), med.get("prescriber_email"), med.get("pharmacy"),
                    med.get("pharmacy_email"), med.get("last_refill"), med.get("days_supply"),
                    med.get("refill_due"),
                    json.dumps(adherence) if isinstance(adherence, (list, dict)) else adherence,
                    med.get("active", 1),
                ),
            )

        for appt in data.get("appointments", []):
            appt_id = appt.get("appt_id") or f"appt_{uuid4().hex[:8]}"
            conn.execute(
                """
                INSERT INTO appointments (
                    appt_id, patient_id, provider, specialty, last_visit,
                    next_scheduled, recommended_frequency_months,
                    clinic_address, phone, clinic_email, active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, 1))
                ON CONFLICT(appt_id) DO UPDATE SET
                    patient_id=excluded.patient_id, provider=excluded.provider,
                    specialty=excluded.specialty, last_visit=excluded.last_visit,
                    next_scheduled=excluded.next_scheduled,
                    recommended_frequency_months=excluded.recommended_frequency_months,
                    clinic_address=excluded.clinic_address, phone=excluded.phone,
                    clinic_email=excluded.clinic_email, active=excluded.active
                """,
                (
                    appt_id, patient_id, appt.get("provider"), appt.get("specialty"),
                    appt.get("last_visit"), appt.get("next_scheduled"),
                    appt.get("recommended_frequency_months"), appt.get("clinic_address"),
                    appt.get("phone"), appt.get("clinic_email"), appt.get("active", 1),
                ),
            )

        for ec in data.get("emergency_contacts", []):
            conn.execute(
                """
                INSERT INTO emergency_contacts (patient_id, name, relation, phone, active)
                VALUES (?, ?, ?, ?, COALESCE(?, 1))
                """,
                (patient_id, ec.get("name"), ec.get("relation"), ec.get("phone"), ec.get("active", 1)),
            )

        for note in data.get("caregiver_notes", []):
            conn.execute(
                """
                INSERT INTO caregiver_notes (patient_id, caregiver_id, date, note, active)
                VALUES (?, ?, ?, ?, COALESCE(?, 1))
                """,
                (patient_id, note.get("caregiver_id"), note.get("date"), note.get("note"), note.get("active", 1)),
            )

        grocery = data.get("grocery")
        if grocery:
            dietary = grocery.get("dietary_restrictions", grocery.get("dietary_restrictions_json", []))
            conn.execute(
                """
                INSERT INTO grocery (patient_id, dietary_restrictions_json, last_delivery)
                VALUES (?, ?, ?)
                ON CONFLICT(patient_id) DO UPDATE SET
                    dietary_restrictions_json=excluded.dietary_restrictions_json,
                    last_delivery=excluded.last_delivery
                """,
                (
                    patient_id,
                    json.dumps(dietary) if isinstance(dietary, (list, dict)) else dietary,
                    grocery.get("last_delivery"),
                ),
            )
            for staple in grocery.get("staples", []):
                conn.execute(
                    """
                    INSERT INTO grocery_staples (patient_id, item, frequency_days, last_ordered, active)
                    VALUES (?, ?, ?, ?, COALESCE(?, 1))
                    """,
                    (
                        patient_id, staple.get("item"), staple.get("frequency_days"),
                        staple.get("last_ordered"), staple.get("active", 1),
                    ),
                )

        financial = data.get("financial", {})
        for bill in financial.get("bills", []):
            conn.execute(
                """
                INSERT INTO financial_bills (patient_id, name, amount, due_date, autopay, active)
                VALUES (?, ?, ?, ?, COALESCE(?, 0), COALESCE(?, 1))
                """,
                (
                    patient_id, bill.get("name"), bill.get("amount"), bill.get("due_date"),
                    bill.get("autopay", 0), bill.get("active", 1),
                ),
            )

        conn.commit()
    return patient_id


def serialize_life_graph(patient_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        patient_row = conn.execute(
            "SELECT * FROM patients WHERE patient_id=? LIMIT 1", (patient_id,)
        ).fetchone()
        if not patient_row:
            return {}
        patient = dict(patient_row)

        medications = _rows_to_dicts(
            conn.execute(
                "SELECT * FROM medications WHERE patient_id=? AND active=1", (patient_id,)
            ).fetchall()
        )
        for m in medications:
            m["adherence_log"] = _json_load(m.get("adherence_log_json"), [])

        appointments = _rows_to_dicts(
            conn.execute(
                "SELECT * FROM appointments WHERE patient_id=? AND active=1", (patient_id,)
            ).fetchall()
        )

        emergency_contacts = _rows_to_dicts(
            conn.execute(
                "SELECT * FROM emergency_contacts WHERE patient_id=? AND active=1", (patient_id,)
            ).fetchall()
        )

        caregiver_notes = _rows_to_dicts(
            conn.execute(
                "SELECT * FROM caregiver_notes WHERE patient_id=? AND active=1", (patient_id,)
            ).fetchall()
        )

        grocery_row = conn.execute(
            "SELECT * FROM grocery WHERE patient_id=? LIMIT 1", (patient_id,)
        ).fetchone()
        grocery = dict(grocery_row) if grocery_row else {}
        if grocery:
            grocery["dietary_restrictions"] = _json_load(grocery.get("dietary_restrictions_json"), [])

        grocery_staples = _rows_to_dicts(
            conn.execute(
                "SELECT * FROM grocery_staples WHERE patient_id=? AND active=1", (patient_id,)
            ).fetchall()
        )

        financial_bills = _rows_to_dicts(
            conn.execute(
                "SELECT * FROM financial_bills WHERE patient_id=? AND active=1", (patient_id,)
            ).fetchall()
        )

        financial_anomalies = _rows_to_dicts(
            conn.execute(
                "SELECT * FROM financial_anomalies WHERE patient_id=?", (patient_id,)
            ).fetchall()
        )

        caregiver_ids = [
            row["caregiver_id"]
            for row in conn.execute(
                "SELECT caregiver_id FROM patient_caregivers WHERE patient_id=?", (patient_id,)
            ).fetchall()
        ]

    return {
        "patient_id": patient_id,
        "name": patient.get("name"),
        "age": patient.get("age"),
        "address": patient.get("address"),
        "preferences": _json_load(patient.get("preferences_json"), {}),
        "emergency_contacts": emergency_contacts,
        "medications": medications,
        "caregiver_notes": caregiver_notes,
        "appointments": appointments,
        "grocery": {**grocery, "staples": grocery_staples},
        "financial": {
            "bills": financial_bills,
            "anomalies": financial_anomalies,
        },
        "assigned_caregivers": caregiver_ids,
    }


def serialize_complete_life_graph(patient_id: str) -> dict[str, Any]:
    """
    Build the complete life graph for a patient, including all linked entities.

    Linked entities include caregivers/schedules, updates, actions, action chat,
    notifications, and expiration notifications related to this patient.
    """
    with get_connection() as conn:
        patient_row = conn.execute(
            "SELECT * FROM patients WHERE patient_id=? LIMIT 1",
            (patient_id,),
        ).fetchone()
        if not patient_row:
            return {}

        patient = dict(patient_row)
        preferences = _json_load(patient.get("preferences_json"), {})

        caregiver_links_rows = conn.execute(
            """
            SELECT patient_id, caregiver_id
            FROM patient_caregivers
            WHERE patient_id=?
            ORDER BY caregiver_id ASC
            """,
            (patient_id,),
        ).fetchall()
        caregiver_links = _rows_to_dicts(caregiver_links_rows)
        caregiver_ids = [row["caregiver_id"] for row in caregiver_links_rows]

        caregivers: list[dict[str, Any]] = []
        caregiver_schedule: list[dict[str, Any]] = []
        if caregiver_ids:
            placeholders = ",".join(["?"] * len(caregiver_ids))
            caregivers = _rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT *
                    FROM caregivers
                    WHERE caregiver_id IN ({placeholders})
                    ORDER BY caregiver_id ASC
                    """,
                    caregiver_ids,
                ).fetchall()
            )
            caregiver_schedule = _rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT *
                    FROM caregiver_schedule
                    WHERE caregiver_id IN ({placeholders})
                    ORDER BY date ASC, start_time ASC, id ASC
                    """,
                    caregiver_ids,
                ).fetchall()
            )

        patient_updates = _rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM patient_updates
                WHERE patient_id=?
                ORDER BY created_at DESC, id DESC
                """,
                (patient_id,),
            ).fetchall()
        )
        for row in patient_updates:
            row["fields_changed"] = _json_load(row.get("fields_changed"), [])

        actions = _rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM action_history
                WHERE patient_id=?
                ORDER BY created_at DESC, action_id ASC
                """,
                (patient_id,),
            ).fetchall()
        )
        for row in actions:
            row["api_payload"] = _json_load(row.get("api_payload"), None)
        action_ids = [row["action_id"] for row in actions if row.get("action_id")]

        action_chat: list[dict[str, Any]] = []
        expiration_notifications: list[dict[str, Any]] = []
        if action_ids:
            placeholders = ",".join(["?"] * len(action_ids))
            action_chat = _rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT *
                    FROM action_chat
                    WHERE action_id IN ({placeholders})
                    ORDER BY id ASC
                    """,
                    action_ids,
                ).fetchall()
            )
            expiration_notifications = _rows_to_dicts(
                conn.execute(
                    f"""
                    SELECT *
                    FROM expiration_notifications
                    WHERE action_id IN ({placeholders})
                    ORDER BY notified_at DESC, id DESC
                    """,
                    action_ids,
                ).fetchall()
            )

        notifications = _rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM notifications
                WHERE patient_id=?
                ORDER BY created_at DESC, id DESC
                """,
                (patient_id,),
            ).fetchall()
        )

    return {
        "patient": {
            "patient_id": patient.get("patient_id"),
            "name": patient.get("name"),
            "age": patient.get("age"),
            "address": patient.get("address"),
            "active": patient.get("active", 1),
            "created_at": patient.get("created_at"),
            "preferences": preferences,
        },
        "assigned_caregivers": caregiver_ids,
        "caregiver_links": caregiver_links,
        "caregivers": caregivers,
        "caregiver_schedule": caregiver_schedule,
        "patient_updates": patient_updates,
        "actions": actions,
        "action_chat": action_chat,
        "notifications": notifications,
        "expiration_notifications": expiration_notifications,
    }


# Patient update helpers
def write_patient_update(update: dict[str, Any]) -> int:
    proposed = update.get("proposed_changes")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO patient_updates (
                patient_id, caregiver_id, domain, operation, fields_changed,
                summary, proposed_changes, confirmed, applied
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                update.get("patient_id"),
                update.get("caregiver_id"),
                update.get("domain"),
                update.get("operation"),
                json.dumps(update.get("fields_changed", [])),
                update.get("summary"),
                json.dumps(proposed) if proposed is not None else None,
                update.get("confirmed", 0),
                update.get("applied", 0),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def append_ingest_audit_row(
    patient_id: str,
    *,
    source: str,
    detect_status: str,
    filename: str | None = None,
) -> int:
    """
    Log a completed ingest/merge in patient_updates (confirmed+applied) so
    /patients/{id}/update-history can show intake alongside staged LLM updates.
    """
    if source == "file":
        label = f"File intake ({filename or 'upload'})"
    else:
        label = "Text intake"
    summary = f"{label} — record merged. Detection: {detect_status}."
    meta: dict[str, Any] = {
        "ingest": True,
        "source": source,
        "detect_status": detect_status,
    }
    if filename:
        meta["filename"] = filename
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO patient_updates (
                patient_id, caregiver_id, domain, operation, fields_changed,
                summary, proposed_changes, confirmed, applied
            ) VALUES (?, NULL, 'general', ?, '[]', ?, ?, 1, 1)
            """,
            (patient_id, f"ingest_{source}", summary, json.dumps(meta)),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_patient_update(update_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM patient_updates WHERE id=? LIMIT 1", (update_id,)
        ).fetchone()
    result = _row_to_dict(row)
    if result:
        result["fields_changed"] = _json_load(result.get("fields_changed"), [])
        result["proposed_changes"] = _json_load(result.get("proposed_changes"), {})
    return result


def confirm_patient_update(update_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE patient_updates SET confirmed=1 WHERE id=?", (update_id,))
        conn.commit()


def deactivate_medication(med_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE medications SET active=0 WHERE med_id=?", (med_id,))
        conn.commit()


def deactivate_appointment(appt_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE appointments SET active=0 WHERE appt_id=?", (appt_id,))
        conn.commit()


def deactivate_caregiver_note(note_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE caregiver_notes SET active=0 WHERE id=?", (note_id,))
        conn.commit()


def deactivate_grocery_staple(staple_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE grocery_staples SET active=0 WHERE id=?", (staple_id,))
        conn.commit()


def deactivate_financial_bill(bill_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE financial_bills SET active=0 WHERE id=?", (bill_id,))
        conn.commit()


# financial_anomalies intentionally omitted: it is a history/audit table with no active column;
# anomaly rows are never removed via the patient-update path.
_SUBTABLE_DEACTIVATORS = {
    "medications": ("med_id", deactivate_medication),
    "appointments": ("appt_id", deactivate_appointment),
    "caregiver_notes": ("id", deactivate_caregiver_note),
    "grocery_staples": ("id", deactivate_grocery_staple),
    "financial_bills": ("id", deactivate_financial_bill),
}


def apply_patient_update(update_id: int, changes: dict[str, Any]) -> None:
    update = get_patient_update(update_id)
    if not update:
        return
    patient_id = update["patient_id"]
    operation = update.get("operation")
    if operation and str(operation).startswith("ingest_"):
        return
    if operation == "remove":
        for table, (pk_field, deactivate_fn) in _SUBTABLE_DEACTIVATORS.items():
            for item in changes.get(table, []):
                if item.get("active") == 0 or pk_field in item:
                    pk_val = item.get(pk_field)
                    if pk_val is not None:
                        deactivate_fn(pk_val)
        if not any(changes.get(t) for t in _SUBTABLE_DEACTIVATORS):
            with get_connection() as conn:
                conn.execute("UPDATE patients SET active=0 WHERE patient_id=?", (patient_id,))
        with get_connection() as conn:
            conn.execute("UPDATE patient_updates SET applied=1 WHERE id=?", (update_id,))
            conn.commit()
        return
    if changes.get("active") == 0 or changes.get("remove") is True:
        with get_connection() as conn:
            conn.execute("UPDATE patients SET active=0 WHERE patient_id=?", (patient_id,))
            conn.execute("UPDATE patient_updates SET applied=1 WHERE id=?", (update_id,))
            conn.commit()
        return

    write_patient({"patient_id": patient_id, **changes})
    with get_connection() as conn:
        conn.execute("UPDATE patient_updates SET applied=1 WHERE id=?", (update_id,))
        conn.commit()


def get_patient_update_history(patient_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM patient_updates
            WHERE patient_id=?
            ORDER BY created_at DESC, id DESC
            """,
            (patient_id,),
        ).fetchall()
    results = _rows_to_dicts(rows)
    for row in results:
        row["fields_changed"] = _json_load(row.get("fields_changed"), [])
        row["proposed_changes"] = _json_load(row.get("proposed_changes"), {})
    return results


# Action helpers
def _action_id(action: dict[str, Any]) -> str:
    return action.get("action_id") or f"act_{uuid4().hex[:12]}"


def write_action(action: dict[str, Any]) -> str:
    action_id = _action_id(action)
    caregiver_options = action.get("caregiver_options_json")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO action_history (
                action_id, patient_id, domain, type, description, draft_content, draft_version,
                modification_in_progress, urgency_level, review_by, invocation_date, is_overdue,
                escalation_count, reviewed, completed, completion_date, assigned_caregiver,
                caregiver_options_json, outcome, manual_action_type, api_payload,
                recipient_email, recipient_type, email_subject, schedule, last_modified_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            ON CONFLICT(action_id) DO UPDATE SET
                patient_id=excluded.patient_id,
                domain=excluded.domain,
                type=excluded.type,
                description=excluded.description,
                draft_content=excluded.draft_content,
                draft_version=excluded.draft_version,
                modification_in_progress=excluded.modification_in_progress,
                urgency_level=excluded.urgency_level,
                review_by=excluded.review_by,
                invocation_date=excluded.invocation_date,
                is_overdue=excluded.is_overdue,
                escalation_count=excluded.escalation_count,
                reviewed=excluded.reviewed,
                completed=excluded.completed,
                completion_date=excluded.completion_date,
                assigned_caregiver=excluded.assigned_caregiver,
                caregiver_options_json=excluded.caregiver_options_json,
                outcome=excluded.outcome,
                manual_action_type=excluded.manual_action_type,
                api_payload=excluded.api_payload,
                recipient_email=excluded.recipient_email,
                recipient_type=excluded.recipient_type,
                email_subject=excluded.email_subject,
                schedule=excluded.schedule,
                last_modified_at=strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            """,
            (
                action_id,
                action.get("patient_id"),
                action.get("domain"),
                action.get("type"),
                action.get("description"),
                action.get("draft_content"),
                action.get("draft_version", 1),
                action.get("modification_in_progress", 0),
                action.get("urgency_level", "tier_3"),
                action.get("review_by"),
                action.get("invocation_date"),
                action.get("is_overdue", 0),
                action.get("escalation_count", 0),
                action.get("reviewed", 0),
                action.get("completed", 0),
                action.get("completion_date"),
                action.get("assigned_caregiver"),
                json.dumps(caregiver_options) if isinstance(caregiver_options, (list, dict)) else caregiver_options,
                action.get("outcome"),
                action.get("manual_action_type"),
                json.dumps(action.get("api_payload")) if action.get("api_payload") is not None else None,
                action.get("recipient_email"),
                action.get("recipient_type"),
                action.get("email_subject"),
                json.dumps(action.get("schedule")) if action.get("schedule") is not None else None,
            ),
        )
        conn.commit()
    return action_id


def get_action(action_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM action_history WHERE action_id=? LIMIT 1", (action_id,)
        ).fetchone()
    result = _row_to_dict(row)
    if result:
        result["api_payload"] = _json_load(result.get("api_payload"), None)
    return result


def get_pending_actions(
    patient_id: str | None = None, domain: str | None = None, type: str | None = None
) -> list[dict[str, Any]]:
    query = "SELECT * FROM action_history WHERE completed=0"
    params: list[Any] = []
    if patient_id:
        query += " AND patient_id=?"
        params.append(patient_id)
    if domain:
        query += " AND domain=?"
        params.append(domain)
    if type:
        query += " AND type=?"
        params.append(type)
    query += " ORDER BY created_at ASC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    results = _rows_to_dicts(rows)
    for row in results:
        row["api_payload"] = _json_load(row.get("api_payload"), None)
    return results


def get_overdue_actions() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM action_history
            WHERE completed=0
              AND is_overdue=0
              AND review_by IS NOT NULL
              AND review_by < strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            ORDER BY review_by ASC
            """
        ).fetchall()
    return _rows_to_dicts(rows)


def mark_action_overdue(action_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE action_history
            SET is_overdue=1,
                urgency_level='tier_0',
                escalation_count=COALESCE(escalation_count, 0) + 1
            WHERE action_id=?
            """,
            (action_id,),
        )
        conn.commit()


def update_action(action_id: str, updates: dict[str, Any]) -> None:
    if not updates:
        return
    payload = updates.copy()
    if "api_payload" in payload:
        payload["api_payload"] = (
            json.dumps(payload["api_payload"]) if payload["api_payload"] is not None else None
        )
    if "caregiver_options_json" in payload and isinstance(payload["caregiver_options_json"], (list, dict)):
        payload["caregiver_options_json"] = json.dumps(payload["caregiver_options_json"])
    set_clause = ", ".join([f"{key}=?" for key in payload.keys()])
    with get_connection() as conn:
        conn.execute(
            f"UPDATE action_history SET {set_clause}, last_modified_at=strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE action_id=?",
            [*payload.values(), action_id],
        )
        conn.commit()


def replace_draft(action_id: str, new_draft: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE action_history
            SET draft_content=?,
                draft_version=COALESCE(draft_version, 1) + 1,
                last_modified_at=strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
                modification_in_progress=0
            WHERE action_id=?
            """,
            (new_draft, action_id),
        )
        conn.commit()


def set_modification_in_progress(action_id: str, in_progress: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE action_history SET modification_in_progress=? WHERE action_id=?",
            (1 if in_progress else 0, action_id),
        )
        conn.commit()


def get_action_rankings() -> list[dict[str, Any]]:
    actions = get_pending_actions()
    for action in actions:
        urgency = URGENCY_SCORES.get(action.get("urgency_level", "tier_3"), 0)
        domain_bonus = DOMAIN_PRIORITY.get(action.get("domain", ""), 0)
        overdue_bonus = OVERDUE_SCORE_BOOST if action.get("is_overdue") else 0
        action["score"] = urgency + domain_bonus + overdue_bonus
    return sorted(
        actions,
        key=lambda item: (
            int(item.get("is_overdue", 0)),
            item.get("score", 0),
            item.get("created_at", ""),
        ),
        reverse=True,
    )


def get_completed_autonomous_approved_actions(limit: int = 30) -> list[dict[str, Any]]:
    """
    Autonomous = no manual_action_type. Shown in the action feed after approval so
    the dashboard can display stored approval_execution (mock API / email / gmaps) results.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM action_history
            WHERE completed = 1
              AND (manual_action_type IS NULL OR TRIM(manual_action_type) = '')
              AND IFNULL(outcome, '') = 'approved'
            ORDER BY COALESCE(completion_date, last_modified_at, created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results = _rows_to_dicts(rows)
    for row in results:
        row["api_payload"] = _json_load(row.get("api_payload"), None)
    return results


# Chat helpers
def write_chat_message(action_id: str, role: str, content: str, intent: str | None = None) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO action_chat (action_id, role, content, intent)
            VALUES (?, ?, ?, ?)
            """,
            (action_id, role, content, intent),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_chat_history(action_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM action_chat WHERE action_id=? ORDER BY id ASC", (action_id,)
        ).fetchall()
    return _rows_to_dicts(rows)


def replace_last_agent_message(action_id: str, new_content: str) -> None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id FROM action_chat
            WHERE action_id=? AND role='agent'
            ORDER BY id DESC LIMIT 1
            """,
            (action_id,),
        ).fetchone()
        if not row:
            return
        conn.execute("UPDATE action_chat SET content=? WHERE id=?", (new_content, row["id"]))
        conn.commit()


# Notification helpers
def write_notification(
    type: str, action_id: str, patient_id: str, title: str, body: str
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notifications (type, action_id, patient_id, title, body)
            VALUES (?, ?, ?, ?, ?)
            """,
            (type, action_id, patient_id, title, body),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_unread_notifications() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE read=0 ORDER BY created_at DESC"
        ).fetchall()
    return _rows_to_dicts(rows)


def mark_notification_read(notification_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE notifications SET read=1 WHERE id=?", (notification_id,))
        conn.commit()


def log_expiration_notification(action_id: str, channel: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO expiration_notifications (action_id, notified_at, channel) VALUES (?, ?, ?)",
            (action_id, datetime.utcnow().isoformat() + "Z", channel),
        )
        conn.commit()


def has_been_notified(action_id: str, channel: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM expiration_notifications
            WHERE action_id=? AND channel=?
            LIMIT 1
            """,
            (action_id, channel),
        ).fetchone()
    return bool(row)


# Caregiver helpers
def _today() -> str:
    return datetime.now().date().isoformat()


def get_all_caregivers() -> list[dict[str, Any]]:
    today = _today()
    with get_connection() as conn:
        caregivers = conn.execute("SELECT * FROM caregivers ORDER BY caregiver_id ASC").fetchall()
        schedule_rows = conn.execute(
            """
            SELECT caregiver_id, available, booked
            FROM caregiver_schedule
            WHERE date=?
            """,
            (today,),
        ).fetchall()
    status_map = {row["caregiver_id"]: dict(row) for row in schedule_rows}
    results = _rows_to_dicts(caregivers)
    for caregiver in results:
        status = status_map.get(caregiver["caregiver_id"], {})
        caregiver["availability_today"] = bool(status.get("available", 0))
        caregiver["booked_today"] = bool(status.get("booked", 0))
    return results


def get_caregiver(caregiver_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        caregiver = conn.execute(
            "SELECT * FROM caregivers WHERE caregiver_id=? LIMIT 1", (caregiver_id,)
        ).fetchone()
    result = _row_to_dict(caregiver)
    if not result:
        return {}
    result["assignments"] = get_caregiver_assignments(caregiver_id)
    result["scheduling_tasks"] = get_scheduling_tasks()
    schedule = get_caregiver_schedule(caregiver_id, _today(), _today())
    if schedule:
        result["availability_today"] = bool(schedule[0].get("available", 0))
        result["booked_today"] = bool(schedule[0].get("booked", 0))
    else:
        result["availability_today"] = False
        result["booked_today"] = False
    return result


def get_caregiver_schedule(caregiver_id: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM caregiver_schedule
            WHERE caregiver_id=? AND date BETWEEN ? AND ?
            ORDER BY date ASC
            """,
            (caregiver_id, start_date, end_date),
        ).fetchall()
    return _rows_to_dicts(rows)


_MANUAL_TYPE_TO_DOMAIN: dict[str, str] = {
    "cvs_refill": "health",
    "pharmacy_refill": "health",
    "health_refill": "health",
    "appointment_booking": "appointment",
    "book_appointment": "appointment",
    "clinic_booking": "appointment",
    "grocery_delivery": "grocery",
    "instacart_cart": "grocery",
    "grocery_setup": "grocery",
    "supply_reorder": "grocery",
    "amazon_order": "grocery",
    "amazon_reorder": "grocery",
    "caregiver_availability": "appointment",
    "transport": "appointment",
    "financial_assessment": "financial",
    "caregiver_assignment": "appointment",
}


def _normalize_domain_field(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in ("appointments", "appt", "appts", "scheduling_domain"):
        return "appointment"
    if s in ("health", "appointment", "grocery", "financial"):
        return s
    return s


def _coalesce_action_domain_for_assignment_row(row: dict[str, Any]) -> str:
    """Ensure a non-empty domain for dashboard assignment cards when DB value is null or legacy."""
    d = _normalize_domain_field(row.get("domain"))
    if d in ("health", "appointment", "grocery", "financial"):
        return d
    m = str(row.get("manual_action_type") or "").strip().lower().replace(" ", "_").replace("-", "_")
    if m in _MANUAL_TYPE_TO_DOMAIN:
        return _MANUAL_TYPE_TO_DOMAIN[m]
    t = str(row.get("type") or "").strip().lower()
    if t == "scheduling" or "appointment" in t or t in ("clinic_visit", "check_in", "caregiver_scheduling"):
        return "appointment"
    if "grocery" in t or "instacart" in t:
        return "grocery"
    if "financ" in t:
        return "financial"
    if d:
        return d
    return "health"


def get_caregiver_assignments(caregiver_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT ah.action_id, ah.description, ah.type, ah.schedule,
                   ah.domain, ah.urgency_level, ah.review_by, ah.draft_content,
                   ah.manual_action_type,
                   p.name AS patient_name, c.name AS caregiver_name
            FROM action_history ah
            JOIN patients p ON p.patient_id = ah.patient_id
            JOIN caregivers c ON c.caregiver_id = ah.assigned_caregiver
            WHERE ah.assigned_caregiver = ? AND ah.completed = 0
            ORDER BY ah.created_at DESC
            """,
            (caregiver_id,),
        ).fetchall()
    out = _rows_to_dicts(rows)
    for row in out:
        row["domain"] = _coalesce_action_domain_for_assignment_row(row)
    return out


def get_caregiver_available_slots(date: str, duration_hours: float = 2.0) -> list[dict[str, Any]]:
    _ = duration_hours
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.caregiver_id, c.name, s.date, s.start_time, s.end_time, s.available, s.booked,
                   (SELECT COUNT(*) FROM patient_caregivers pc WHERE pc.caregiver_id=c.caregiver_id) AS assigned_count
            FROM caregiver_schedule s
            JOIN caregivers c ON c.caregiver_id=s.caregiver_id
            WHERE s.date=? AND s.available=1 AND s.booked=0
            ORDER BY assigned_count DESC, s.start_time ASC
            """,
            (date,),
        ).fetchall()
    return _rows_to_dicts(rows)


def get_caregivers_available(start_time: str, end_time: str) -> list[dict[str, Any]]:
    """Return caregivers with at least one available, unbooked slot overlapping [start_time, end_time]."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT c.caregiver_id, c.name, c.email, c.phone, c.role
            FROM caregivers c
            JOIN caregiver_schedule s ON s.caregiver_id = c.caregiver_id
            WHERE s.available = 1 AND s.booked = 0
              AND s.start_time < :end AND s.end_time > :start
            ORDER BY c.name ASC
            """,
            {"start": start_time, "end": end_time},
        ).fetchall()
    return _rows_to_dicts(rows)


def get_caregivers_by_workload() -> list[dict[str, Any]]:
    """Return all caregivers ordered ascending by (assigned_actions + booked_slots)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.caregiver_id, c.name, c.email, c.phone, c.role,
                   (
                     (SELECT COUNT(*) FROM action_history ah
                      WHERE ah.assigned_caregiver = c.caregiver_id AND ah.completed = 0)
                     +
                     (SELECT COUNT(*) FROM caregiver_schedule cs
                      WHERE cs.caregiver_id = c.caregiver_id AND cs.booked = 1)
                   ) AS load
            FROM caregivers c
            ORDER BY load ASC, c.name ASC
            """,
        ).fetchall()
    return _rows_to_dicts(rows)


_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def create_caregiver(
    name: str,
    email: str,
    phone: str,
    role: str,
    schedule: dict,  # {"Mon": {"start": "09:00", "end": "17:00"}, ...}
) -> str:
    import secrets
    from datetime import date as _date, timedelta as _timedelta

    caregiver_id = "cg_" + secrets.token_hex(3)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO caregivers (caregiver_id, name, email, phone, role) VALUES (?,?,?,?,?)",
            (caregiver_id, name, email, phone, role),
        )
        today = _date.today()
        for i in range(14):
            target = today + _timedelta(days=i)
            day_entry = schedule.get(_DAY_NAMES[target.weekday()])
            conn.execute(
                """
                INSERT INTO caregiver_schedule
                    (caregiver_id, date, start_time, end_time, available, booked)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    caregiver_id,
                    target.isoformat(),
                    day_entry["start"] if day_entry else None,
                    day_entry["end"] if day_entry else None,
                    1 if day_entry else 0,
                ),
            )
        conn.commit()
    return caregiver_id


def book_caregiver_slot(caregiver_id: str, date: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE caregiver_schedule SET booked=1 WHERE caregiver_id=? AND date=?",
            (caregiver_id, date),
        )
        conn.commit()


def free_caregiver_slot(caregiver_id: str, date: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE caregiver_schedule SET booked=0 WHERE caregiver_id=? AND date=?",
            (caregiver_id, date),
        )
        conn.commit()


def get_scheduling_tasks() -> list[dict[str, Any]]:
    tasks = get_pending_actions(type="scheduling_task")
    for task in tasks:
        task["score"] = (
            URGENCY_SCORES.get(task.get("urgency_level", "tier_3"), 0)
            + DOMAIN_PRIORITY.get(task.get("domain", "scheduling"), 0)
            + (OVERDUE_SCORE_BOOST if task.get("is_overdue") else 0)
        )
    return sorted(
        tasks,
        key=lambda item: (
            int(item.get("is_overdue", 0)),
            item.get("score", 0),
            item.get("created_at", ""),
        ),
        reverse=True,
    )


def get_latest_pending_scheduling_action(requester_address: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM action_history
            WHERE type='scheduling_task' AND completed=0
            ORDER BY created_at DESC
            """
        ).fetchall()
    for row in _rows_to_dicts(rows):
        payload = _json_load(row.get("api_payload"), {})
        if isinstance(payload, dict) and payload.get("requester_address") == requester_address:
            row["api_payload"] = payload
            return row
    return None


# ---------------------------------------------------------------------------
# General chat session helpers
# ---------------------------------------------------------------------------

def create_session(session_id: str) -> str:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO chat_sessions (id) VALUES (?)",
            (session_id,),
        )
        conn.commit()
    return session_id


def write_chat_session_message(
    session_id: str,
    role: str,
    content: str,
    stage: str = "",
    intent_class: str | None = None,
    domain: str | None = None,
    patient_ids: list[str] | None = None,
    draft_action_id: str | None = None,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_messages
              (session_id, role, content, stage, intent_class, domain, patient_ids, draft_action_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                stage,
                intent_class,
                domain,
                json.dumps(patient_ids) if patient_ids is not None else None,
                draft_action_id,
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def get_session_messages(session_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id=? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    msgs = _rows_to_dicts(rows)
    for m in msgs:
        m["patient_ids"] = _json_load(m.get("patient_ids"), [])
    return msgs


def session_exists(session_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM chat_sessions WHERE id=? LIMIT 1", (session_id,)
        ).fetchone()
    return row is not None


def write_staged_action(session_id: str, draft_payload: dict[str, Any]) -> str:
    draft_id = f"draft_{uuid4().hex[:12]}"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO staged_actions (id, session_id, draft_payload, status)
            VALUES (?, ?, ?, 'pending_approval')
            """,
            (draft_id, session_id, json.dumps(draft_payload)),
        )
        conn.commit()
    return draft_id


def get_staged_action(draft_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM staged_actions WHERE id=? LIMIT 1", (draft_id,)
        ).fetchone()
    if not row:
        return None
    result = _row_to_dict(row)
    result["draft_payload"] = _json_load(result.get("draft_payload"), {})
    return result


def update_staged_action_payload(draft_id: str, draft_payload: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE staged_actions SET draft_payload=? WHERE id=?",
            (json.dumps(draft_payload), draft_id),
        )
        conn.commit()


def update_staged_action_status(draft_id: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE staged_actions SET status=? WHERE id=?",
            (status, draft_id),
        )
        conn.commit()


def commit_staged_to_action_history(draft_id: str) -> str:
    staged = get_staged_action(draft_id)
    if not staged or staged.get("status") != "pending_approval":
        raise ValueError(f"Staged action {draft_id!r} not found or not pending_approval")
    payload = staged["draft_payload"]
    action_id = write_action(payload)
    update_staged_action_status(draft_id, "committed")
    return action_id


def expire_old_staged_actions(max_age_hours: int = 24) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE staged_actions SET status='discarded'
            WHERE status='pending_approval'
              AND created_at < datetime('now', ?)
            """,
            (f"-{max_age_hours} hours",),
        )
        conn.commit()
        return cursor.rowcount
