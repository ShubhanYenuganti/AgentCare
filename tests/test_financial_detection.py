"""Unit tests for financial domain detection logic.

Tests _parse_drafts with deterministic seed financial data.
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


def _patient_with_financial() -> str:
    from agents.shared.db import write_patient
    return write_patient({
        "name": "Robert Kim",
        "age": 77,
        "address": "4 Maple Dr",
    })


def _make_draft(type_: str, urgency: str = "tier_2") -> dict:
    return {
        "type": type_,
        "description": f"Financial action: {type_}",
        "draft_content": f"Address {type_} for patient.",
        "urgency_level": urgency,
        "manual_action_type": None,
        "api_payload": None,
        "recipient_email": None,
        "recipient_type": None,
        "email_subject": None,
    }


class TestFinancialDetection:
    def test_parse_bill_due_alert_draft(self):
        """_parse_drafts produces ActionDraft with bill_due_alert type."""
        from agents.financial.worker import _parse_drafts

        patient_id = _patient_with_financial()
        raw = [_make_draft("bill_due_alert", "tier_2")]
        pass_id = "fin-pass-001"
        drafts = _parse_drafts(raw, patient_id, pass_id)
        assert any("bill" in d.type or "due" in d.type for d in drafts)
        assert drafts[0].domain == "financial"

    def test_parse_missed_autopay_draft(self):
        """_parse_drafts handles missed_autopay type."""
        from agents.financial.worker import _parse_drafts

        patient_id = _patient_with_financial()
        raw = [_make_draft("missed_autopay", "tier_1")]
        drafts = _parse_drafts(raw, patient_id, "fin-pass-002")
        assert any("autopay" in d.type or "missed" in d.type for d in drafts)

    def test_parse_spending_anomaly_draft(self):
        """_parse_drafts handles spending_anomaly type."""
        from agents.financial.worker import _parse_drafts

        patient_id = _patient_with_financial()
        raw = [_make_draft("spending_anomaly", "tier_2")]
        drafts = _parse_drafts(raw, patient_id, "fin-pass-003")
        assert any("spending" in d.type or "anomaly" in d.type for d in drafts)

    def test_empty_response_returns_empty_list(self):
        """_parse_drafts returns empty list for empty input (stub applied at caller level)."""
        from agents.financial.worker import _parse_drafts

        patient_id = _patient_with_financial()
        drafts = _parse_drafts([], patient_id, "fin-pass-004")
        assert isinstance(drafts, list)
        assert len(drafts) == 0

    def test_draft_urgency_tier1_preserved(self):
        """tier_1 urgency is preserved through parse pipeline."""
        from agents.financial.worker import _parse_drafts

        patient_id = _patient_with_financial()
        raw = [_make_draft("bill_due_alert", "tier_1")]
        drafts = _parse_drafts(raw, patient_id, "fin-pass-005")
        assert drafts[0].urgency_level == "tier_1"

    def test_multiple_financial_drafts_parsed(self):
        """Multiple drafts in LLM output are all parsed."""
        from agents.financial.worker import _parse_drafts

        patient_id = _patient_with_financial()
        raw = [
            _make_draft("bill_due_alert"),
            _make_draft("missed_autopay"),
            _make_draft("spending_anomaly"),
        ]
        drafts = _parse_drafts(raw, patient_id, "fin-pass-006")
        assert len(drafts) == 3
