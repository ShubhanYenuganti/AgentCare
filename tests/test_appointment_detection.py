"""Unit tests for appointment domain detection logic.

Tests _parse_detection_response with deterministic seed data.
"""

from __future__ import annotations

import os
import tempfile

import pytest

_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SQLITE_DB_PATH", _tmp)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["SQLITE_DB_PATH"] = db_path
    from agents.shared.db import init_db
    init_db()
    yield
    os.environ["SQLITE_DB_PATH"] = _tmp


def _patient() -> str:
    from agents.shared.db import write_patient
    return write_patient({"name": "John Doe", "age": 80, "address": "2 Oak Ave"})


def _make_draft(type_: str, urgency: str = "tier_2") -> dict:
    return {
        "type": type_,
        "description": f"Appointment action: {type_}",
        "draft_content": f"Address {type_} for patient.",
        "urgency_level": urgency,
        "manual_action_type": None,
        "api_payload": None,
        "recipient_email": None,
        "recipient_type": None,
        "email_subject": None,
    }


class TestAppointmentDetection:
    def test_parse_overdue_appointment_draft(self):
        """_parse_detection_response produces ActionDraft with overdue_appointment type."""
        from agents.appointment.worker import _parse_detection_response

        patient_id = _patient()
        raw = [_make_draft("overdue_appointment", "tier_1")]
        drafts = _parse_detection_response(raw, patient_id)
        assert any("appointment" in d.type or "overdue" in d.type for d in drafts)
        assert drafts[0].domain == "appointment"

    def test_parse_transport_planning_draft(self):
        """_parse_detection_response handles transport planning type."""
        from agents.appointment.worker import _parse_detection_response

        patient_id = _patient()
        raw = [_make_draft("transport_planning", "tier_2")]
        drafts = _parse_detection_response(raw, patient_id)
        assert any("transport" in d.type for d in drafts)

    def test_parse_visit_prep_draft(self):
        """_parse_detection_response handles visit prep type."""
        from agents.appointment.worker import _parse_detection_response

        patient_id = _patient()
        raw = [_make_draft("visit_prep", "tier_3")]
        drafts = _parse_detection_response(raw, patient_id)
        assert any("visit" in d.type or "prep" in d.type for d in drafts)

    def test_empty_response_returns_stub(self):
        """Empty LLM response produces stub draft."""
        from agents.appointment.worker import _parse_detection_response

        patient_id = _patient()
        drafts = _parse_detection_response([], patient_id)
        assert len(drafts) >= 1
        assert drafts[0].domain == "appointment"

    def test_draft_urgency_preserved(self):
        """Urgency level from LLM response is preserved in ActionDraft."""
        from agents.appointment.worker import _parse_detection_response

        patient_id = _patient()
        raw = [_make_draft("overdue_appointment", "tier_1")]
        drafts = _parse_detection_response(raw, patient_id)
        assert drafts[0].urgency_level == "tier_1"

    def test_maps_key_absent_fallback_stub(self):
        """When Maps key is absent, transport planning still produces a draft (no exception)."""
        from agents.appointment.worker import _parse_detection_response

        patient_id = _patient()
        # Simulate transport planning even when GOOGLE_MAPS_API_KEY is missing
        os.environ.pop("GOOGLE_MAPS_API_KEY", None)
        raw = [_make_draft("transport_planning")]
        drafts = _parse_detection_response(raw, patient_id)
        assert len(drafts) >= 1
