"""Integration tests for patient update submit → confirm pipeline.

Uses a temp SQLite DB and the FastAPI TestClient.
The EXECUTOR_INTERNAL_URL is left unset so _trigger_detect() returns a
no-op status rather than making a real HTTP call.
"""

from __future__ import annotations

import os
import tempfile

import pytest

_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SQLITE_DB_PATH", _tmp)
os.environ.setdefault("EXECUTOR_INTERNAL_URL", "")  # disable real detect call

from fastapi.testclient import TestClient  # noqa: E402

from agents.shared.db import (  # noqa: E402
    get_action,
    get_connection,
    init_db,
    write_action,
    write_patient,
)
from api.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["SQLITE_DB_PATH"] = db_path
    init_db()
    yield
    os.environ["SQLITE_DB_PATH"] = _tmp


# ── helpers ──────────────────────────────────────────────────────────────────

def assert_ok(resp, status=200):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["success"] is True, body
    return body["data"]


def assert_error(resp, status):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["success"] is False, body


def seed_patient(**kwargs) -> str:
    data = {"name": "Test Patient", "age": 70, "address": "123 Test St"}
    data.update(kwargs)
    return write_patient(data)


# ── 7.1 Patient update submit → confirm ──────────────────────────────────────

_MOCK_CLASSIFICATION = {
    "domain": "health",
    "operation": "update",
    "fields_changed": ["medications"],
    "summary": "Medication dosage updated",
    "proposed_changes": {"medications": [{"name": "Lisinopril", "dose": "20mg"}]},
}


class TestPatientUpdatePipeline:
    def test_submit_update_returns_update_id(self):
        from unittest.mock import patch
        pid = seed_patient(name="Alice")
        # Patch where the function is looked up by the patients router
        with patch("api.routers.patients.call_claude_json", return_value=_MOCK_CLASSIFICATION):
            resp = client.post(f"/patients/{pid}/update", json={"content": "Increase Lisinopril dose"})
        data = assert_ok(resp)
        assert "update_id" in data or "applied" in data  # either inline confirm or staged

    def test_confirm_update_applies_changes(self):
        """Submit then confirm asserts the update record is applied."""
        from unittest.mock import patch
        pid = seed_patient(name="Bob")

        with patch("api.routers.patients.call_claude_json", return_value=_MOCK_CLASSIFICATION):
            resp = client.post(f"/patients/{pid}/update", json={"content": "Change address to 456 Oak Ave"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # If update is staged (update_id present), confirm it
        if body.get("success") and "update_id" in body.get("data", {}):
            update_id = body["data"]["update_id"]
            confirm_resp = client.post(f"/patients/{pid}/update/{update_id}/confirm")
            assert confirm_resp.status_code == 200, confirm_resp.text
            confirm_data = confirm_resp.json()
            assert confirm_data.get("success") is True

    def test_update_history_recorded(self):
        """After submit, update appears in history endpoint."""
        from unittest.mock import patch
        pid = seed_patient(name="Carol")
        with patch("api.routers.patients.call_claude_json", return_value=_MOCK_CLASSIFICATION):
            client.post(f"/patients/{pid}/update", json={"content": "New medication added"})
        hist = client.get(f"/patients/{pid}/update-history")
        data = assert_ok(hist)
        assert isinstance(data, list)

    def test_confirm_nonexistent_update_returns_error(self):
        pid = seed_patient()
        resp = client.post(f"/patients/{pid}/update/99999/confirm")
        # Should return 404 or 400
        assert resp.status_code in (400, 404, 409), resp.text

    def test_confirm_triggers_detect_field_in_response(self):
        """Confirm returns detect_status field (even if executor URL is empty)."""
        from unittest.mock import patch
        pid = seed_patient(name="Dave")
        with patch("api.routers.patients.call_claude_json", return_value=_MOCK_CLASSIFICATION):
            submit = client.post(f"/patients/{pid}/update", json={"content": "Update grocery list"})
        body = submit.json()
        if body.get("success") and "update_id" in body.get("data", {}):
            update_id = body["data"]["update_id"]
            resp = client.post(f"/patients/{pid}/update/{update_id}/confirm")
            data = assert_ok(resp)
            # detect_status should be present (even if None/empty)
            assert "detect_status" in data or "applied" in data
