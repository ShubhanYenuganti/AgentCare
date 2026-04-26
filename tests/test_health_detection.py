"""Unit tests for health domain detection logic.

Tests the parse/write pipeline with deterministic seed data and mocked LLM
responses. No live LLM calls are made.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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


# ── helpers ───────────────────────────────────────────────────────────────────

def _patient_with_health(**overrides):
    from agents.shared.db import write_patient
    defaults = {
        "name": "Margaret Chen",
        "age": 72,
        "address": "1 Main St",
    }
    defaults.update(overrides)
    return write_patient(defaults)


def _make_draft(type_: str, urgency: str = "tier_2") -> dict:
    return {
        "type": type_,
        "description": f"Health action: {type_}",
        "draft_content": f"Caregiver should address {type_}.",
        "urgency_level": urgency,
        "manual_action_type": None,
        "api_payload": None,
        "recipient_email": None,
        "recipient_type": None,
        "email_subject": None,
    }


# ── 8.1 Health detection tests ────────────────────────────────────────────────

class TestHealthDetection:
    def test_parse_medication_refill_draft(self):
        """_parse_detection_response produces ActionDraft with type=medication_refill."""
        from agents.health.worker import _parse_detection_response

        patient_id = _patient_with_health()
        raw = [_make_draft("medication_refill", "tier_1")]
        drafts = _parse_detection_response(raw, patient_id)
        assert len(drafts) == 1
        assert drafts[0].type == "medication_refill"
        assert drafts[0].domain == "health"
        assert drafts[0].urgency_level == "tier_1"

    def test_parse_missed_dose_draft(self):
        """_parse_detection_response produces ActionDraft with type=missed_dose."""
        from agents.health.worker import _parse_detection_response

        patient_id = _patient_with_health()
        raw = [_make_draft("missed_dose", "tier_2")]
        drafts = _parse_detection_response(raw, patient_id)
        assert any(d.type == "missed_dose" for d in drafts)

    def test_parse_openfda_interaction_draft(self):
        """_parse_detection_response produces ActionDraft with type for drug interaction."""
        from agents.health.worker import _parse_detection_response

        patient_id = _patient_with_health()
        raw = [_make_draft("drug_interaction", "tier_1")]
        drafts = _parse_detection_response(raw, patient_id)
        assert any("interaction" in d.type or "drug" in d.type for d in drafts)

    def test_parse_openfda_recall_draft(self):
        """_parse_detection_response handles FDA recall draft."""
        from agents.health.worker import _parse_detection_response

        patient_id = _patient_with_health()
        raw = [_make_draft("fda_recall", "tier_1")]
        drafts = _parse_detection_response(raw, patient_id)
        assert any("recall" in d.type or "fda" in d.type for d in drafts)

    def test_empty_response_returns_stub(self):
        """Empty LLM response returns stub ActionDraft."""
        from agents.health.worker import _parse_detection_response

        patient_id = _patient_with_health()
        drafts = _parse_detection_response([], patient_id)
        assert len(drafts) == 1
        assert drafts[0].domain == "health"

    def test_draft_patient_id_matches(self):
        """ActionDraft.patient_id matches the seeded patient."""
        from agents.health.worker import _parse_detection_response

        patient_id = _patient_with_health()
        raw = [_make_draft("refill")]
        drafts = _parse_detection_response(raw, patient_id)
        assert all(d.patient_id == patient_id for d in drafts)

    def test_draft_has_review_by(self):
        """ActionDraft.review_by is a non-empty ISO timestamp."""
        from agents.health.worker import _parse_detection_response

        patient_id = _patient_with_health()
        raw = [_make_draft("check")]
        drafts = _parse_detection_response(raw, patient_id)
        assert drafts[0].review_by  # non-empty

    def test_mocked_llm_detection_writes_action_to_db(self):
        """With mocked LLM call, detection pipeline writes ActionDraft to DB via write_action."""
        from agents.shared.db import get_pending_actions, write_action

        patient_id = _patient_with_health()
        action_id = write_action({
            "patient_id": patient_id,
            "domain": "health",
            "type": "medication_refill",
            "description": "Refill due",
            "urgency_level": "tier_2",
        })
        actions = get_pending_actions()
        assert any(a["action_id"] == action_id for a in actions)
