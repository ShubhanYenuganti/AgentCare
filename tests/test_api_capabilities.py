"""Unit tests for API capability catalog + draft validation."""

from __future__ import annotations

from agents.shared.api_capabilities import (
    API_PAYLOAD_TEMPLATE_VERSION,
    build_api_payload_template,
    infer_primary_route_for_action,
    resolve_route_and_params_from_action,
    validate_detection_draft_for_api_requirements,
    worker_api_capability_block,
)


def test_infer_primary_route_from_manual_action_type():
    route = infer_primary_route_for_action(
        {
            "domain": "health",
            "manual_action_type": "cvs_refill",
            "api_payload": build_api_payload_template("POST /mock/cvs/refill"),
        }
    )
    assert route == "POST /mock/cvs/refill"


def test_resolve_template_payload_extracts_parameter_values():
    payload = build_api_payload_template("POST /mock/cal/book")
    payload["call"]["parameters"] = {
        "provider": {"value": "Dr. Anita Patel"},
        "patient_id": {"value": "pt_001"},
        "preferred_times": {"value": ["morning"]},
    }
    route, params, errors, source = resolve_route_and_params_from_action(
        {
            "domain": "appointment",
            "manual_action_type": "appointment_booking",
            "api_payload": payload,
        }
    )
    assert route == "POST /mock/cal/book"
    assert params["provider"] == "Dr. Anita Patel"
    assert params["preferred_times"] == ["morning"]
    assert errors == []
    assert source == "template_v1"


def test_validate_api_draft_requires_template_fields_for_mock_route():
    errors = validate_detection_draft_for_api_requirements(
        {
            "domain": "appointment",
            "manual_action_type": "appointment_booking",
            "api_payload": {
                "template_version": API_PAYLOAD_TEMPLATE_VERSION,
                "call": {
                    "route_key": "POST /mock/cal/book",
                    "provider": "mock",
                    "parameters": {
                        "provider": {"value": "Dr. Anita Patel"},
                        "patient_id": {"value": "pt_001"},
                    },
                },
            },
            "recipient_email": None,
            "recipient_type": None,
        }
    )
    assert "missing api_payload.call.parameters.preferred_times" in errors
    assert "missing recipient_email" not in errors
    assert "missing recipient_type" not in errors


def test_validate_email_route_requires_recipient_fields():
    payload = build_api_payload_template("POST resend:/emails", provider="live")
    payload["call"]["parameters"] = {
        "to": {"value": "patient@example.com"},
        "subject": {"value": "Care update"},
        "html": {"value": "<p>hello</p>"},
    }

    errors = validate_detection_draft_for_api_requirements(
        {
            "domain": "health",
            "manual_action_type": None,
            "api_payload": payload,
            "recipient_email": None,
            "recipient_type": None,
        }
    )
    assert "missing recipient_email" in errors
    assert "missing recipient_type" in errors
    assert "missing email_subject" in errors


def test_validate_known_recipient_email_enforced():
    payload = build_api_payload_template("POST /mock/amazon/order")
    payload["call"]["parameters"] = {
        "patient_id": {"value": "pt_001"},
        "items": {"value": ["paper towels"]},
    }

    errors = validate_detection_draft_for_api_requirements(
        {
            "domain": "grocery",
            "manual_action_type": "amazon_order",
            "api_payload": payload,
            "recipient_email": "unknown@example.com",
            "recipient_type": "caregiver",
            "email_subject": "Household order ready",
        },
        known_recipient_emails={"known@example.com"},
    )
    assert "unknown recipient_email='unknown@example.com'" in errors


def test_validate_non_api_draft_returns_no_errors():
    errors = validate_detection_draft_for_api_requirements(
        {
            "domain": "financial",
            "manual_action_type": None,
            "api_payload": None,
            "recipient_email": None,
            "recipient_type": None,
        }
    )
    assert errors == []


def test_validate_non_api_email_draft_still_requires_subject_and_known_recipient():
    errors = validate_detection_draft_for_api_requirements(
        {
            "domain": "financial",
            "manual_action_type": None,
            "api_payload": None,
            "recipient_email": "unknown@example.com",
            "recipient_type": "caregiver",
            "email_subject": None,
        },
        known_recipient_emails={"known@example.com"},
    )
    assert "missing email_subject" in errors
    assert "unknown recipient_email='unknown@example.com'" in errors


def test_worker_api_capability_block_mentions_domain_routes_and_template():
    block = worker_api_capability_block("appointment")
    assert "GET /mock/cal/available" in block
    assert "POST /mock/cal/book" in block
    assert '"template_version": "v1"' in block
