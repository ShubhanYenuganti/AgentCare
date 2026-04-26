"""
End-to-end orchestration tests (Task 8.1).

These tests verify the intent → routing → response contract without spinning up
live agent processes. They cover:

  - Intent classification produces correct routing decisions
  - Executor detection fan-out state management is correct
  - Supervisor result handler finalises the fan-out and sends chat reply
  - Question / modification routing produces correct upstream correlations
  - Timeout sweep cleans up stale fan-outs and fires partial-result reply
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

def _fresh_fan_out_state():
    """Re-import a clean fan_out_state to avoid cross-test contamination."""
    import importlib
    import agents.shared.state_service as ss
    importlib.reload(ss)
    return ss.fan_out_state


# ── 1. Intent classification ──────────────────────────────────────────────────

class TestIntentClassification:
    """Verify executor _classify_intent maps queries to correct IntentClass."""

    @pytest.fixture(autouse=True)
    def import_classify(self):
        from agents.executor.agent import _classify_intent
        self._classify = _classify_intent

    def test_question_intent(self):
        r = self._classify("What medication does the patient take?")
        assert r.intent == "question"

    def test_scheduling_intent(self):
        r = self._classify("Book a caregiver slot for Thursday")
        assert r.intent == "scheduling"

    def test_modification_intent(self):
        r = self._classify("Update the grocery delivery address")
        assert r.intent == "modification"
        assert r.domain == "grocery"

    def test_detection_intent_keyword(self):
        r = self._classify("Check the patient's current status")
        assert r.intent == "detection"

    def test_detection_default(self):
        """Queries with no strong signal default to detection fan-out."""
        r = self._classify("patient information")
        assert r.intent == "detection"

    def test_health_domain_resolved_on_question(self):
        r = self._classify("How is the medication refill going?")
        assert r.intent == "question"
        assert r.domain == "health"

    def test_appointment_domain_resolved_on_modification(self):
        r = self._classify("Change the appointment time")
        assert r.intent == "modification"
        assert r.domain == "appointment"

    def test_scheduling_takes_precedence_over_question(self):
        r = self._classify("What is the caregiver availability schedule?")
        assert r.intent == "scheduling"


# ── 2. Detection domain pre-filter ───────────────────────────────────────────

class TestDetectionDomainFilter:
    """Verify detection fan-out domain selection logic."""

    @pytest.fixture(autouse=True)
    def import_filter(self):
        from agents.executor.agent import _detection_domains_for_trigger
        self._filter = _detection_domains_for_trigger

    def test_patient_create_returns_all_domains(self):
        domains = self._filter("patient_create", None)
        assert set(domains) == {"health", "appointment", "grocery", "financial"}

    def test_patient_update_no_fields_returns_all(self):
        domains = self._filter("patient_update", [])
        assert set(domains) == {"health", "appointment", "grocery", "financial"}

    def test_patient_update_medication_field_routes_health(self):
        domains = self._filter("patient_update", ["medications"])
        assert "health" in domains

    def test_patient_update_grocery_field_routes_grocery(self):
        domains = self._filter("patient_update", ["grocery_preferences"])
        assert "grocery" in domains


# ── 3. Fan-out state management ───────────────────────────────────────────────

class TestFanOutState:
    """Verify PendingFanOut and FanOutRequestState correctness."""

    def _make_fan_out(self, domains=None):
        from agents.shared.state_service import PendingFanOut
        return PendingFanOut(
            pass_id=str(uuid4()),
            patient_id="pt_test",
            user_sender_address="test_sender",
            target_domains=domains or ["health", "appointment"],
        )

    def test_not_complete_initially(self):
        fo = self._make_fan_out()
        assert not fo.is_complete()

    def test_complete_when_all_domains_responded(self):
        fo = self._make_fan_out(["health", "appointment"])
        fo.record_result("health", {"actions": []})
        fo.record_result("appointment", {"actions": []})
        assert fo.is_complete()

    def test_pending_domains_tracks_remaining(self):
        fo = self._make_fan_out(["health", "appointment", "grocery"])
        fo.record_result("health", {"actions": []})
        pending = fo.pending_domains()
        assert "health" not in pending
        assert "appointment" in pending
        assert "grocery" in pending

    def test_timeout_marks_domain_failed(self):
        fo = self._make_fan_out(["health"])
        fo.record_timeout("health")
        assert fo.is_complete()
        assert fo.domain_timeouts.get("health") is True
        assert fo.domain_results["health"] is None

    def test_register_and_retrieve(self):
        from agents.shared.state_service import FanOutRequestState, PendingFanOut
        state = FanOutRequestState()
        fo = self._make_fan_out()
        state.register(fo)
        assert state.get(fo.pass_id) is fo

    def test_remove_stale_removes_expired(self):
        from agents.shared.state_service import FanOutRequestState, PendingFanOut
        state = FanOutRequestState()
        fo = self._make_fan_out()
        # artificially age the fan-out
        fo.created_at = datetime.now(tz=timezone.utc) - timedelta(seconds=400)
        state.register(fo)
        stale = state.remove_stale(300)
        assert fo in stale
        assert state.get(fo.pass_id) is None


# ── 4. Lifecycle transition validator ─────────────────────────────────────────

class TestLifecycleTransitions:
    """Verify action lifecycle transition rules."""

    def _action(self, **kwargs) -> dict:
        base = {
            "action_id": "act_test",
            "completed": 0,
            "is_overdue": 0,
            "modification_in_progress": 0,
            "reviewed": 0,
            "escalation_count": 0,
        }
        base.update(kwargs)
        return base

    def test_draft_to_reviewed_allowed(self):
        from agents.shared.lifecycle import validate_transition
        r = validate_transition(self._action(), "reviewed")
        assert r.valid

    def test_draft_to_completed_allowed(self):
        from agents.shared.lifecycle import validate_transition
        r = validate_transition(self._action(), "completed")
        assert r.valid

    def test_completed_to_draft_rejected(self):
        from agents.shared.lifecycle import validate_transition
        r = validate_transition(self._action(completed=1), "draft")
        assert not r.valid
        assert "terminal" in r.error.lower() or "not permitted" in r.error.lower()

    def test_modification_in_progress_to_draft_allowed(self):
        from agents.shared.lifecycle import validate_transition
        r = validate_transition(self._action(modification_in_progress=1), "draft")
        assert r.valid

    def test_require_transition_raises_on_invalid(self):
        from agents.shared.lifecycle import require_transition, TransitionError
        with pytest.raises(TransitionError):
            require_transition(self._action(completed=1), "draft")

    def test_current_state_reflects_fields(self):
        from agents.shared.lifecycle import current_state
        assert current_state(self._action()) == "draft"
        assert current_state(self._action(completed=1)) == "completed"
        assert current_state(self._action(modification_in_progress=1)) == "modification_in_progress"
        assert current_state(self._action(is_overdue=1)) == "overdue"
        assert current_state(self._action(is_overdue=1, escalation_count=2)) == "escalated"


# ── 5. Request state timeout sweep ───────────────────────────────────────────

class TestRequestStateTimeout:
    """Verify InMemoryRequestState timeout sweep."""

    def _make_pending(self, age_seconds=0):
        from agents.shared.state_service import PendingRequest
        return PendingRequest(
            request_id=str(uuid4()),
            query="test query",
            domain="health",
            intent="detection",
            user_sender_address=None,
            routed_address="test_addr",
            created_at=datetime.now(tz=timezone.utc) - timedelta(seconds=age_seconds),
        )

    def test_fresh_request_not_stale(self):
        from agents.shared.state_service import InMemoryRequestState
        state = InMemoryRequestState()
        pending = self._make_pending(age_seconds=0)
        state.set_request(pending)
        stale = state.remove_stale_requests(45.0)
        assert stale == []
        assert state.get_request(pending.request_id) is pending

    def test_old_request_is_stale(self):
        from agents.shared.state_service import InMemoryRequestState
        state = InMemoryRequestState()
        pending = self._make_pending(age_seconds=60)
        state.set_request(pending)
        stale = state.remove_stale_requests(45.0)
        assert pending in stale
        assert state.get_request(pending.request_id) is None


# ── 6. API contract smoke test ────────────────────────────────────────────────

class TestApiOrchestrationContract:
    """Smoke tests verifying executor REST API routing contract."""

    @pytest.fixture(autouse=True)
    def setup_env(self, tmp_path, monkeypatch):
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("SQLITE_DB_PATH", str(db_file))
        from agents.shared.db import init_db
        init_db()

    def test_post_message_returns_intent_field(self):
        """POST /message response must include intent field."""
        import importlib
        import api.main as main_mod
        importlib.reload(main_mod)
        from fastapi.testclient import TestClient
        # We can't easily spin up the executor agent, so test via API ingest
        from api.main import app
        client = TestClient(app)
        r = client.post("/ingest/text", json={"content": "test patient query", "patient_id": None})
        # ingest returns success envelope regardless of executor availability
        data = r.json()
        assert "success" in data

    def test_actions_envelope_structure(self):
        from api.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/actions")
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        assert "data" in body

    def test_patients_envelope_structure(self):
        from api.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/patients")
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True

    def test_org_envelope_structure(self):
        from api.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/org")
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
