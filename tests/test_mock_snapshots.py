"""Mock-path snapshot tests.

Capture the current mock/shared infrastructure state so regressions during
Sprint 2 migration are caught immediately.
"""

from __future__ import annotations

import os

import pytest


# ---------------------------------------------------------------------------
# Test 1: MockDomainTask model fields
# ---------------------------------------------------------------------------

def _get_fields(model_cls) -> set:
    """Return field names for a uagents Model (pydantic v1 style uses __fields__)."""
    # uagents Model is pydantic v1-based; pydantic v2 uses model_fields.
    # Support both by trying pydantic v2 first, falling back to v1.
    if hasattr(model_cls, "model_fields"):
        return set(model_cls.model_fields.keys())
    return set(model_cls.__fields__.keys())


def test_mock_domain_task_fields() -> None:
    """MockDomainTask must expose the expected field names."""
    from agents.shared.models import MockDomainTask

    fields = _get_fields(MockDomainTask)
    for expected in ("request_id", "domain", "query", "user_sender_address", "metadata"):
        assert expected in fields, f"MockDomainTask is missing field: {expected}"


# ---------------------------------------------------------------------------
# Test 2: MockSupervisorResult fields
# ---------------------------------------------------------------------------

def test_mock_supervisor_result_fields() -> None:
    """MockSupervisorResult must expose the expected field names."""
    from agents.shared.models import MockSupervisorResult

    fields = _get_fields(MockSupervisorResult)
    for expected in ("request_id", "domain", "supervisor", "result"):
        assert expected in fields, f"MockSupervisorResult is missing field: {expected}"


# ---------------------------------------------------------------------------
# Test 3: MockWorkerResult fields
# ---------------------------------------------------------------------------

def test_mock_worker_result_fields() -> None:
    """MockWorkerResult must expose the expected field names."""
    from agents.shared.models import MockWorkerResult

    fields = _get_fields(MockWorkerResult)
    for expected in ("request_id", "domain", "worker", "result"):
        assert expected in fields, f"MockWorkerResult is missing field: {expected}"


# ---------------------------------------------------------------------------
# Test 4: DOMAIN_KEYWORDS snapshot
# ---------------------------------------------------------------------------

def test_domain_keywords_health() -> None:
    """DOMAIN_KEYWORDS['health'] must contain 'health' and 'medication'."""
    from agents.shared.constants import DOMAIN_KEYWORDS

    health_kws = DOMAIN_KEYWORDS["health"]
    assert "health" in health_kws, "'health' missing from DOMAIN_KEYWORDS['health']"
    assert "medication" in health_kws, "'medication' missing from DOMAIN_KEYWORDS['health']"


# ---------------------------------------------------------------------------
# Test 5: AGENT_PORTS snapshot
# ---------------------------------------------------------------------------

def test_agent_ports_snapshot() -> None:
    """All expected agent ports must match the canonical values."""
    from agents.shared.constants import AGENT_PORTS

    expected_ports = {
        "executor": 8001,
        "health_supervisor": 8101,
        "health_worker": 8102,
        "appointment_supervisor": 8201,
        "appointment_worker": 8202,
        "grocery_supervisor": 8301,
        "grocery_worker": 8302,
        "financial_supervisor": 8401,
        "financial_worker": 8402,
        "scheduling_agent": 8501,
    }

    for agent, expected_port in expected_ports.items():
        actual = AGENT_PORTS.get(agent)
        assert actual == expected_port, (
            f"AGENT_PORTS[{agent!r}]: expected {expected_port}, got {actual}"
        )


# ---------------------------------------------------------------------------
# Test 6: Production models importable
# ---------------------------------------------------------------------------

def test_production_models_importable() -> None:
    """All production model classes must be importable from agents.shared.models."""
    from agents.shared.models import (  # noqa: F401
        SupervisorResult,
        OnDemandDetectionRequest,
        ModificationRequest,
        QuestionRequest,
        WorkerResult,
        ActionDraft,
    )


def test_detection_request_fields() -> None:
    """OnDemandDetectionRequest must include full and filtered context fields."""
    from agents.shared.models import OnDemandDetectionRequest

    fields = _get_fields(OnDemandDetectionRequest)
    for expected in (
        "patient_id",
        "trigger",
        "pass_id",
        "updated_domain",
        "org_context",
        "patient_snapshot",
        "snapshot_meta",
        "domain_patient_context",
    ):
        assert expected in fields, f"OnDemandDetectionRequest missing field: {expected}"


# ---------------------------------------------------------------------------
# Test 7: IntentRoutingResult importable
# ---------------------------------------------------------------------------

def test_intent_routing_result_importable() -> None:
    """IntentRoutingResult must be importable from agents.shared.models."""
    from agents.shared.models import IntentRoutingResult  # noqa: F401


# ---------------------------------------------------------------------------
# Test 8: Lifecycle validator importable
# ---------------------------------------------------------------------------

def test_validate_transition_importable() -> None:
    """validate_transition must be importable from agents.shared.lifecycle."""
    from agents.shared.lifecycle import validate_transition  # noqa: F401


# ---------------------------------------------------------------------------
# Test 9: DB helpers present
# ---------------------------------------------------------------------------

def test_db_helpers_importable() -> None:
    """Core DB helpers must be importable from agents.shared.db."""
    from agents.shared.db import write_action, get_action, get_all_patients  # noqa: F401


# ---------------------------------------------------------------------------
# Test 10: LLM helpers present
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
def test_llm_helpers_importable() -> None:
    """call_claude and call_claude_json must be importable from agents.shared.llm."""
    from agents.shared.llm import call_claude, call_claude_json  # noqa: F401


def test_llm_module_importable_without_key() -> None:
    """The llm module itself must import without an API key (lazy client init)."""
    import importlib
    import agents.shared.llm  # noqa: F401

    # If we got here without an exception, the module loads fine.
    assert True
