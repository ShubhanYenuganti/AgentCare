"""Integration tests for the MACOS FastAPI backend.

Uses an in-memory SQLite DB so production data is never touched.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Point to a temp DB before any app imports so _db_path() resolves correctly.
_tmp = tempfile.mktemp(suffix=".db")
os.environ["SQLITE_DB_PATH"] = _tmp

from fastapi.testclient import TestClient  # noqa: E402

from agents.shared.db import (  # noqa: E402
    init_db,
    write_action,
    write_notification,
    write_patient,
)
from api.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Initialise a fresh schema before every test."""
    init_db()
    yield


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

def assert_success(resp, status=200):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "data" in body
    return body["data"]


def assert_error(resp, status):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["success"] is False
    assert "error" in body


# ---------------------------------------------------------------------------
# GET /actions
# ---------------------------------------------------------------------------

def test_get_actions_empty():
    data = assert_success(client.get("/actions"))
    assert isinstance(data, list)


def test_get_actions_with_record():
    write_action({"patient_id": "pt_test", "domain": "health", "type": "reminder", "urgency_level": "tier_2"})
    data = assert_success(client.get("/actions"))
    assert len(data) >= 1


# ---------------------------------------------------------------------------
# GET /actions/{action_id}
# ---------------------------------------------------------------------------

def test_get_action_not_found():
    assert_error(client.get("/actions/nonexistent"), 404)


def test_get_action_found():
    action_id = write_action({"domain": "health", "type": "reminder"})
    data = assert_success(client.get(f"/actions/{action_id}"))
    assert data["action_id"] == action_id


# ---------------------------------------------------------------------------
# PATCH /actions/{action_id}
# ---------------------------------------------------------------------------

def test_patch_action_mark_reviewed():
    action_id = write_action({"domain": "health", "type": "reminder"})
    data = assert_success(client.patch(f"/actions/{action_id}", json={"reviewed": True}))
    assert data["reviewed"] == 1


def test_patch_action_not_found():
    assert_error(client.patch("/actions/ghost", json={"reviewed": True}), 404)


def test_patch_action_idempotency_key_deduplication():
    """Sending the same idempotency_key twice must return the same action without re-processing."""
    action_id = write_action({"domain": "health", "type": "email"})
    payload = {
        "idempotency_key": "idem-abc-123",
        "modification_instruction": "Change subject to urgent",
    }

    resp1 = client.patch(f"/actions/{action_id}", json=payload)
    data1 = assert_success(resp1)

    # Second call with same key — should be idempotent
    resp2 = client.patch(f"/actions/{action_id}", json=payload)
    data2 = assert_success(resp2)

    # Both responses reference the same action; the idempotency_key is stored
    assert data1["action_id"] == data2["action_id"]
    stored_payload = data1.get("api_payload") or {}
    assert stored_payload.get("idempotency_key") == "idem-abc-123"


# ---------------------------------------------------------------------------
# POST /actions/{action_id}/complete
# ---------------------------------------------------------------------------

def test_complete_action():
    action_id = write_action({"domain": "health", "type": "reminder"})
    data = assert_success(client.post(f"/actions/{action_id}/complete"))
    assert data["completed"] == 1


def test_complete_action_not_found():
    assert_error(client.post("/actions/ghost/complete"), 404)


# ---------------------------------------------------------------------------
# GET /patients
# ---------------------------------------------------------------------------

def test_get_patients_empty():
    data = assert_success(client.get("/patients"))
    assert isinstance(data, list)


def test_get_patients_with_record():
    write_patient({"name": "Alice"})
    data = assert_success(client.get("/patients"))
    assert len(data) >= 1


# ---------------------------------------------------------------------------
# POST /patients + GET /patients/{patient_id}
# ---------------------------------------------------------------------------

def test_create_patient_and_fetch():
    resp = client.post("/patients", json={"name": "Bob", "age": 72, "address": "1 Main St"})
    created = assert_success(resp)
    assert created["name"] == "Bob"
    patient_id = created["patient_id"]

    fetched = assert_success(client.get(f"/patients/{patient_id}"))
    assert fetched["patient_id"] == patient_id
    assert fetched["name"] == "Bob"


def test_get_patient_not_found():
    assert_error(client.get("/patients/no-such-pt"), 404)


# ---------------------------------------------------------------------------
# PUT /patients/{patient_id}
# ---------------------------------------------------------------------------

def test_update_patient():
    patient_id = write_patient({"name": "Carol", "age": 65})
    data = assert_success(client.put(f"/patients/{patient_id}", json={"name": "Carol Updated"}))
    assert data["name"] == "Carol Updated"


# ---------------------------------------------------------------------------
# GET /caregivers
# ---------------------------------------------------------------------------

def test_get_caregivers_empty():
    data = assert_success(client.get("/caregivers"))
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------

def test_get_notifications_empty():
    data = assert_success(client.get("/notifications"))
    assert isinstance(data, list)


def test_get_notifications_with_record():
    write_notification("alert", "act_1", "pt_1", "Test Title", "Test Body")
    data = assert_success(client.get("/notifications"))
    assert len(data) >= 1


# ---------------------------------------------------------------------------
# POST /notifications/{id}/read
# ---------------------------------------------------------------------------

def test_mark_notification_read():
    nid = write_notification("alert", "act_1", "pt_1", "T", "B")
    resp = client.post(f"/notifications/{nid}/read")
    body = assert_success(resp)
    assert body is None

    # Notification should no longer appear in unread list
    unread = assert_success(client.get("/notifications"))
    ids = [n["id"] for n in unread]
    assert nid not in ids


# ---------------------------------------------------------------------------
# GET /org
# ---------------------------------------------------------------------------

def test_get_org():
    data = assert_success(client.get("/org"))
    # May be empty dict if no org row exists yet
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# PATCH /org
# ---------------------------------------------------------------------------

def test_patch_org():
    data = assert_success(client.patch("/org", json={"org_name": "Sunrise Care"}))
    assert data["org_name"] == "Sunrise Care"


# ---------------------------------------------------------------------------
# GET /scheduling/tasks
# ---------------------------------------------------------------------------

def test_get_scheduling_tasks_empty():
    data = assert_success(client.get("/scheduling/tasks"))
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# POST /ingest/text (no executor configured)
# ---------------------------------------------------------------------------

def test_ingest_text_queued():
    resp = client.post("/ingest/text", json={"content": "Patient missed medication", "patient_id": "pt_1"})
    data = assert_success(resp)
    assert data["status"] == "queued"


# ---------------------------------------------------------------------------
# Mock APIs
# ---------------------------------------------------------------------------

def test_mock_cvs_available():
    resp = client.get("/mock/cvs/available", params={"doctor_name": "Dr. Anita Patel"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["doctor_name"] == "Dr. Anita Patel"
    assert "available_medications" in body
    assert body["total_available"] >= 1


def test_mock_cvs_available_requires_doctor_name():
    resp = client.get("/mock/cvs/available")
    assert resp.status_code == 422


def test_mock_cal_available_and_book():
    avail = client.get(
        "/mock/cal/available",
        params={"patient_id": "pt_001", "doctor_name": "Dr. Anita Patel"},
    )
    assert avail.status_code == 200
    avail_body = avail.json()
    assert avail_body["doctor_name"] == "Dr. Anita Patel"
    assert "slots" in avail_body
    assert isinstance(avail_body["slots"], list)

    book = client.post(
        "/mock/cal/book",
        json={
            "provider": "Dr. Anita Patel",
            "patient_id": "pt_001",
            "preferred_times": ["morning"],
        },
    )
    assert book.status_code == 200
    assert book.json().get("status") == "booked"


def test_mock_cal_available_requires_doctor_name():
    resp = client.get("/mock/cal/available", params={"patient_id": "pt_001"})
    assert resp.status_code == 422


def test_mock_amazon_order_and_reorder_alias():
    payload = {"patient_id": "pt_001", "items": ["paper towels"], "dietary_flags": []}

    order = client.post("/mock/amazon/order", json=payload)
    assert order.status_code == 200
    assert order.json().get("status") == "cart_created"

    alias = client.post("/mock/amazon/reorder", json=payload)
    assert alias.status_code == 200
    assert alias.json().get("status") == "cart_created"


# ---------------------------------------------------------------------------
# POST /actions/{action_id}/approve
# ---------------------------------------------------------------------------

def test_approve_action_success(monkeypatch):
    from api.routers import actions as actions_router

    patient_id = write_patient({"patient_id": "pt_001", "name": "Margaret Chen"})
    action_id = write_action(
        {
            "action_id": "act_approve_success",
            "patient_id": patient_id,
            "domain": "health",
            "type": "detection",
            "description": "Refill due",
            "manual_action_type": "cvs_refill",
            "api_payload": {
                "template_version": "v1",
                "call": {
                    "route_key": "POST /mock/cvs/refill",
                    "provider": "mock",
                    "parameters": {
                        "medication": {"value": "Lisinopril 10mg"},
                        "patient_id": {"value": patient_id},
                        "pharmacy": {"value": "CVS Mission St"},
                    },
                },
            },
            "recipient_email": "pharmacy@example.com",
            "recipient_type": "pharmacy",
            "email_subject": "Refill request: Lisinopril for Margaret Chen",
        }
    )

    async def fake_execute(action):
        return {"success": True, "steps": [{"step": "mock", "ok": True}], "failed_required_steps": []}

    monkeypatch.setattr(actions_router, "_execute_approved_action", fake_execute)
    resp = client.post(f"/actions/{action_id}/approve")
    data = assert_success(resp)
    assert data["action"]["completed"] == 1
    assert data["execution"]["success"] is True


def test_approve_action_failure(monkeypatch):
    from api.routers import actions as actions_router

    action_id = write_action(
        {
            "action_id": "act_approve_fail",
            "patient_id": "pt_001",
            "domain": "grocery",
            "type": "detection",
            "description": "Create grocery cart",
            "manual_action_type": "grocery_delivery",
            "api_payload": {
                "template_version": "v1",
                "call": {
                    "route_key": "POST /mock/instacart/cart",
                    "provider": "mock",
                    "parameters": {
                        "patient_id": {"value": "pt_001"},
                        "items": {"value": ["spinach"]},
                    },
                },
            },
            "recipient_email": "caregiver@example.com",
            "recipient_type": "caregiver",
            "email_subject": "Grocery cart created for patient",
        }
    )

    async def fake_execute(action):
        return {
            "success": False,
            "steps": [{"step": "mock", "ok": False}],
            "failed_required_steps": [{"step": "mock", "ok": False}],
        }

    monkeypatch.setattr(actions_router, "_execute_approved_action", fake_execute)
    resp = client.post(f"/actions/{action_id}/approve")
    assert resp.status_code == 502
    body = resp.json()
    assert body["success"] is False
    assert "data" in body
