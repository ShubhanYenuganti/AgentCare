"""E2E tests for scheduling lifecycle via REST API.

Tests the full scheduling lifecycle: assign → unconfirmed → confirm/decline
status transitions using FastAPI TestClient and real SQLite.
"""

from __future__ import annotations

import os
import tempfile

import pytest

_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SQLITE_DB_PATH", _tmp)
os.environ.setdefault("EXECUTOR_INTERNAL_URL", "")

from fastapi.testclient import TestClient  # noqa: E402

from agents.shared.db import (  # noqa: E402
    get_action,
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


def assert_ok(resp, status=200):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["success"] is True, body
    return body["data"]


def seed_scheduling_action(caregiver_id: str | None = None) -> str:
    """Create a patient and scheduling action in pending_approval state."""
    patient_id = write_patient({"name": "Scheduling Patient", "age": 70})
    action_id = write_action({
        "patient_id": patient_id,
        "domain": "appointment",
        "type": "scheduling",
        "description": "Schedule a care visit",
        "urgency_level": "tier_2",
        "manual_action_type": "scheduling",
        "scheduling_status": "pending_approval",
    })
    if caregiver_id:
        from agents.shared.db import update_action
        update_action(action_id, {
            "assigned_caregiver": caregiver_id,
            "scheduling_status": "unconfirmed",
        })
    return action_id


def seed_caregiver() -> str:
    """Insert a test caregiver and return caregiver_id."""
    from agents.shared.db import get_connection
    caregiver_id = "test_caregiver_001"
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO caregivers (caregiver_id, name) VALUES (?, ?)",
            (caregiver_id, "Test Caregiver"),
        )
        conn.commit()
    return caregiver_id


# ── 9.1 Full scheduling selection flow ───────────────────────────────────────

class TestSchedulingSelectionFlow:
    def test_assign_transitions_to_unconfirmed(self):
        """POST /scheduling/{id}/assign → scheduling_status=unconfirmed."""
        caregiver_id = seed_caregiver()
        action_id = seed_scheduling_action()

        resp = client.post(f"/scheduling/{action_id}/assign", json={"caregiver_id": caregiver_id})
        data = assert_ok(resp)
        assert data["scheduling_status"] == "unconfirmed"
        assert data["assigned_caregiver"] == caregiver_id

    def test_confirm_after_assign_sets_confirmed_and_completed(self):
        """Assign then confirm → scheduling_status=confirmed, completed=1."""
        caregiver_id = seed_caregiver()
        action_id = seed_scheduling_action(caregiver_id=caregiver_id)

        resp = client.post(f"/scheduling/{action_id}/confirm")
        data = assert_ok(resp)
        assert data["scheduling_status"] == "confirmed"
        assert data["completed"] == 1

    def test_assign_non_pending_action_returns_409(self):
        """Assigning an action not in pending_approval returns 409."""
        caregiver_id = seed_caregiver()
        action_id = seed_scheduling_action(caregiver_id=caregiver_id)
        # Already unconfirmed — reassign should fail
        resp = client.post(f"/scheduling/{action_id}/assign", json={"caregiver_id": caregiver_id})
        assert resp.status_code == 409, resp.text


# ── 9.2 Cancel flow ──────────────────────────────────────────────────────────

class TestSchedulingCancelFlow:
    def test_cancel_pending_action_sets_cancelled_status(self):
        """POST /scheduling/{id}/cancel → scheduling_status='cancelled', no caregiver assigned."""
        action_id = seed_scheduling_action()  # pending_approval

        resp = client.post(f"/scheduling/{action_id}/cancel")
        data = assert_ok(resp)
        assert data["scheduling_status"] == "cancelled", data
        assert not data.get("assigned_caregiver")

    def test_cancel_unconfirmed_action_also_sets_cancelled(self):
        """Cancelling an unconfirmed (already assigned) action also reaches cancelled state."""
        caregiver_id = seed_caregiver()
        action_id = seed_scheduling_action(caregiver_id=caregiver_id)  # already unconfirmed

        resp = client.post(f"/scheduling/{action_id}/cancel")
        data = assert_ok(resp)
        assert data["scheduling_status"] == "cancelled"
        assert not data.get("assigned_caregiver")

    def test_cancel_nonexistent_action_returns_404(self):
        """Cancelling a nonexistent action returns 404."""
        resp = client.post("/scheduling/nonexistent_id/cancel")
        assert resp.status_code == 404, resp.text

    def test_cancel_already_confirmed_returns_409(self):
        """Cancelling an already-confirmed action returns 409."""
        caregiver_id = seed_caregiver()
        action_id = seed_scheduling_action(caregiver_id=caregiver_id)
        client.post(f"/scheduling/{action_id}/confirm")  # move to confirmed

        resp = client.post(f"/scheduling/{action_id}/cancel")
        assert resp.status_code == 409, resp.text

    def test_cancel_writes_cancelled_status_to_db(self):
        """DB reflects scheduling_status='cancelled' after cancel call."""
        action_id = seed_scheduling_action()
        client.post(f"/scheduling/{action_id}/cancel")
        action = get_action(action_id)
        assert action["scheduling_status"] == "cancelled"

    def test_decline_resets_to_pending_approval(self):
        """POST /scheduling/{id}/decline → scheduling_status=pending_approval, assigned_caregiver=null."""
        caregiver_id = seed_caregiver()
        action_id = seed_scheduling_action(caregiver_id=caregiver_id)

        resp = client.post(f"/scheduling/{action_id}/decline")
        data = assert_ok(resp)
        assert data["scheduling_status"] == "pending_approval"
        assert not data.get("assigned_caregiver")

    def test_decline_unassigned_action_returns_404_or_error(self):
        """Declining a nonexistent action returns 404."""
        resp = client.post("/scheduling/nonexistent_id/decline")
        assert resp.status_code in (404, 400), resp.text


# ── 9.3 REST API E2E: assign → confirm and decline scenarios ─────────────────

class TestSchedulingApiE2E:
    def test_full_assign_confirm_flow(self):
        """assign → confirm produces confirmed + completed=1 in DB."""
        caregiver_id = seed_caregiver()
        action_id = seed_scheduling_action()

        client.post(f"/scheduling/{action_id}/assign", json={"caregiver_id": caregiver_id})
        client.post(f"/scheduling/{action_id}/confirm")

        action = get_action(action_id)
        assert action["scheduling_status"] == "confirmed"
        assert action["completed"] == 1

    def test_decline_clears_caregiver_in_db(self):
        """decline clears assigned_caregiver and resets to pending_approval in DB."""
        caregiver_id = seed_caregiver()
        action_id = seed_scheduling_action(caregiver_id=caregiver_id)

        client.post(f"/scheduling/{action_id}/decline")

        action = get_action(action_id)
        assert action["scheduling_status"] == "pending_approval"
        assert not action.get("assigned_caregiver")

    def test_confirm_non_unconfirmed_returns_409(self):
        """Confirming an action not in unconfirmed state returns 409."""
        action_id = seed_scheduling_action()  # pending_approval, not unconfirmed
        resp = client.post(f"/scheduling/{action_id}/confirm")
        assert resp.status_code == 409, resp.text

    def test_scheduling_action_not_found_returns_404(self):
        """Assign/confirm/decline/cancel on nonexistent action returns 404."""
        for endpoint in ["assign", "confirm", "decline", "cancel"]:
            if endpoint == "assign":
                resp = client.post("/scheduling/bad_id/assign", json={"caregiver_id": "x"})
            else:
                resp = client.post(f"/scheduling/bad_id/{endpoint}")
            assert resp.status_code == 404, f"{endpoint}: {resp.text}"
