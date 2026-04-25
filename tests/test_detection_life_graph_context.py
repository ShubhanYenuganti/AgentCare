"""Detection life-graph context tests."""

from __future__ import annotations


def _setup_db(tmp_path, monkeypatch):
    db_file = tmp_path / "life_graph_test.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_file))
    from agents.shared.db import init_db

    init_db()
    return db_file


def test_find_active_patients_by_name_case_space_insensitive(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    from agents.shared.db import find_active_patients_by_name, write_patient

    write_patient({"patient_id": "pt_001", "name": "Margaret Chen", "active": 1})
    write_patient({"patient_id": "pt_002", "name": "Margaret Chen", "active": 0})

    matches = find_active_patients_by_name("  MARGARET   CHEN ")
    assert len(matches) == 1
    assert matches[0]["patient_id"] == "pt_001"


def test_find_active_patients_by_name_query_supports_unique_partial(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    from agents.shared.db import find_active_patients_by_name_query, write_patient

    write_patient({"patient_id": "pt_001", "name": "Margaret Chen", "active": 1})
    write_patient({"patient_id": "pt_002", "name": "Robert Harris", "active": 1})

    matches = find_active_patients_by_name_query("please run detection for Margaret")
    assert len(matches) == 1
    assert matches[0]["patient_id"] == "pt_001"


def test_find_active_patients_by_name_query_partial_can_be_ambiguous(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    from agents.shared.db import find_active_patients_by_name_query, write_patient

    write_patient({"patient_id": "pt_001", "name": "Margaret Chen", "active": 1})
    write_patient({"patient_id": "pt_002", "name": "Margaret Diaz", "active": 1})

    matches = find_active_patients_by_name_query("run detection for Margaret")
    assert len(matches) == 2
    assert {item["patient_id"] for item in matches} == {"pt_001", "pt_002"}


def test_serialize_complete_life_graph_includes_linked_entities(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    from agents.shared.db import (
        get_connection,
        log_expiration_notification,
        serialize_complete_life_graph,
        write_action,
        write_chat_message,
        write_notification,
        write_patient,
        write_patient_update,
    )

    patient_id = write_patient(
        {
            "patient_id": "pt_001",
            "name": "Margaret Chen",
            "age": 74,
            "pharmacy_name": "CVS Mission St",
            "pharmacy_email": "pharmacy@cvs-mission.example",
            "doctor_name": "Dr. Anita Patel",
            "doctor_email": "dr.anita.patel@exampleclinic.org",
            "preferences": {"appointment_times": ["morning"]},
            "medications": [{"name": "Lisinopril"}],
            "active": 1,
        }
    )
    write_patient_update(
        {
            "patient_id": patient_id,
            "domain": "health",
            "operation": "update",
            "fields_changed": ["medications"],
            "summary": "Updated medications",
            "confirmed": 1,
            "applied": 1,
        }
    )
    health_action_id = write_action(
        {
            "action_id": "act_health_001",
            "patient_id": patient_id,
            "domain": "health",
            "type": "refill",
            "description": "Check refill status",
            "urgency_level": "tier_2",
        }
    )
    write_chat_message(health_action_id, "agent", "Need refill confirmation")
    write_notification("health_alert", health_action_id, patient_id, "Refill", "Check refill")
    log_expiration_notification(health_action_id, "email")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO caregivers (caregiver_id, name, email, phone, asi_one_address, role)
            VALUES ('cg_001', 'Sarah Okafor', 'sarah@example.com', '+1-555-1001', NULL, 'caregiver')
            """
        )
        conn.execute(
            "INSERT INTO patient_caregivers (patient_id, caregiver_id) VALUES (?, 'cg_001')",
            (patient_id,),
        )
        conn.execute(
            """
            INSERT INTO caregiver_schedule (caregiver_id, date, start_time, end_time, available, booked)
            VALUES ('cg_001', '2026-04-25', '08:00', '16:00', 1, 0)
            """
        )
        conn.commit()

    snapshot = serialize_complete_life_graph(patient_id)
    for expected_key in (
        "patient",
        "caregiver_links",
        "caregivers",
        "caregiver_schedule",
        "patient_updates",
        "actions",
        "action_chat",
        "notifications",
        "expiration_notifications",
    ):
        assert expected_key in snapshot
    assert snapshot["patient"]["patient_id"] == patient_id
    assert snapshot["patient"]["pharmacy_email"] == "pharmacy@cvs-mission.example"
    assert snapshot["patient"]["doctor_email"] == "dr.anita.patel@exampleclinic.org"
    assert snapshot["caregivers"][0]["caregiver_id"] == "cg_001"
    assert snapshot["action_chat"][0]["action_id"] == health_action_id
    assert snapshot["notifications"][0]["patient_id"] == patient_id


def test_domain_parser_filters_out_of_scope_sections(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    from agents.shared.life_graph_parser import parse_life_graph_for_domain

    full_snapshot = {
        "patient": {"patient_id": "pt_001", "name": "Margaret Chen"},
        "caregivers": [{"caregiver_id": "cg_001"}],
        "caregiver_schedule": [{"caregiver_id": "cg_001", "date": "2026-04-25"}],
        "patient_updates": [
            {"id": 1, "domain": "health", "summary": "health update"},
            {"id": 2, "domain": "financial", "summary": "financial update"},
        ],
        "actions": [
            {"action_id": "act_health_001", "domain": "health"},
            {"action_id": "act_fin_001", "domain": "financial"},
        ],
        "action_chat": [
            {"action_id": "act_health_001", "content": "health thread"},
            {"action_id": "act_fin_001", "content": "financial thread"},
        ],
        "notifications": [
            {"action_id": "act_health_001", "type": "health_alert"},
            {"action_id": "act_fin_001", "type": "financial_alert"},
        ],
        "expiration_notifications": [
            {"action_id": "act_health_001", "channel": "email"},
            {"action_id": "act_fin_001", "channel": "email"},
        ],
    }

    health_context, health_meta = parse_life_graph_for_domain(full_snapshot, "health")
    assert all(item.get("domain") == "health" for item in health_context["actions"])
    assert len(health_context["actions"]) == 1
    assert health_context["actions"][0]["action_id"] == "act_health_001"
    assert "caregiver_schedule" not in health_context
    assert "caregiver_schedule" in health_meta["dropped_top_level_keys"]

    appt_context, _ = parse_life_graph_for_domain(full_snapshot, "appointment")
    assert "caregiver_schedule" in appt_context
    assert appt_context["actions"] == []
