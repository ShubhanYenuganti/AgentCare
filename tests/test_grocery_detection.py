"""Unit tests for grocery domain detection logic.

Tests _parse_drafts with deterministic seed data.
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
    return write_patient({
        "name": "Mary Green",
        "age": 75,
        "address": "3 Elm St",
    })


def _make_draft(type_: str, urgency: str = "tier_3") -> dict:
    return {
        "type": type_,
        "description": f"Grocery action: {type_}",
        "draft_content": f"Address {type_} for patient.",
        "urgency_level": urgency,
        "manual_action_type": None,
        "api_payload": None,
        "recipient_email": None,
        "recipient_type": None,
        "email_subject": None,
    }


class TestGroceryDetection:
    def test_parse_grocery_reorder_draft(self):
        """_parse_drafts produces ActionDraft with grocery_reorder type."""
        from agents.grocery.worker import _parse_drafts

        patient_id = _patient()
        raw = [_make_draft("grocery_reorder")]
        pass_id = "test-pass-001"
        drafts = _parse_drafts(raw, patient_id, pass_id)
        assert any("reorder" in d.type or "grocery" in d.type for d in drafts)
        assert drafts[0].domain == "grocery"

    def test_parse_delivery_staleness_draft(self):
        """_parse_drafts handles delivery_staleness type (last delivery > 7 days ago)."""
        from agents.grocery.worker import _parse_drafts

        patient_id = _patient()
        raw = [_make_draft("delivery_staleness")]
        drafts = _parse_drafts(raw, patient_id, "pass-002")
        assert any("delivery" in d.type or "stale" in d.type for d in drafts)

    def test_parse_dietary_conflict_draft(self):
        """_parse_drafts handles dietary_conflict type."""
        from agents.grocery.worker import _parse_drafts

        patient_id = _patient()
        raw = [_make_draft("dietary_conflict", "tier_2")]
        drafts = _parse_drafts(raw, patient_id, "pass-003")
        assert any("dietary" in d.type or "conflict" in d.type or "diet" in d.type for d in drafts)

    def test_empty_response_returns_empty_list(self):
        """_parse_drafts returns empty list for empty input (stub applied at caller level)."""
        from agents.grocery.worker import _parse_drafts

        patient_id = _patient()
        drafts = _parse_drafts([], patient_id, "pass-004")
        # _parse_drafts does not add a stub; the caller applies _stub_draft on empty
        assert isinstance(drafts, list)
        assert len(drafts) == 0

    def test_draft_patient_id_correct(self):
        """ActionDraft.patient_id matches seeded patient."""
        from agents.grocery.worker import _parse_drafts

        patient_id = _patient()
        raw = [_make_draft("supply_reorder")]
        drafts = _parse_drafts(raw, patient_id, "pass-005")
        assert all(d.patient_id == patient_id for d in drafts)

    def test_supply_reorder_draft(self):
        """_parse_drafts handles supply_reorder type."""
        from agents.grocery.worker import _parse_drafts

        patient_id = _patient()
        raw = [_make_draft("supply_reorder", "tier_3")]
        drafts = _parse_drafts(raw, patient_id, "pass-006")
        assert any("supply" in d.type or "reorder" in d.type for d in drafts)
