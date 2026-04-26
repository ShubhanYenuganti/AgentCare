"""API capability catalog and payload-template helpers."""

from __future__ import annotations

import json
from typing import Any

API_PAYLOAD_TEMPLATE_VERSION = "v1"

# Canonical execution routes for API-completable actions.
MOCK_ROUTE_SCHEMAS: dict[str, dict[str, Any]] = {
    "POST /mock/cvs/refill": {
        "when": "Medication refill is needed and pharmacy coordination can be automated.",
        "payload_required": ["medication", "patient_id", "pharmacy"],
    },
    "GET /mock/cvs/available": {
        "when": "Before proposing refill actions, check available medications.",
        "query_required": ["doctor_name"],
        "query_optional": ["medication"],
    },
    "GET /mock/cal/available": {
        "when": "Before booking appointment tasks, check provider availability windows.",
        "query_required": ["doctor_name"],
        "query_optional": ["provider", "patient_id"],
    },
    "POST /mock/cal/book": {
        "when": "Appointment booking can be executed with provider and preferred time windows.",
        "payload_required": ["provider", "patient_id", "preferred_times"],
    },
    "POST /mock/instacart/cart": {
        "when": "Create grocery delivery carts based on dietary and staple needs.",
        "payload_required": ["patient_id", "items"],
    },
    "POST /mock/amazon/order": {
        "when": "Create household/supply orders that can be executed through Amazon.",
        "payload_required": ["patient_id", "items"],
    },
    "POST /mock/amazon/reorder": {
        "when": "Backward-compatible alias for Amazon household ordering.",
        "payload_required": ["patient_id", "items"],
    },
    "POST /mock/caregivers/available": {
        "when": "Check caregiver capacity before transport/scheduling assignment actions.",
        "payload_required": ["date", "manual_action_type", "patient_id", "duration_hours"],
    },
}

LIVE_ROUTE_SCHEMAS: dict[str, dict[str, Any]] = {
    "POST resend:/emails": {
        "when": "An action needs outbound email delivery to a specific recipient.",
        "payload_required": ["to", "subject", "html"],
    },
    "GET gmaps:/maps/api/distancematrix/json": {
        "when": "Scheduling agent only: enrich transport/scheduling plans with travel estimates.",
        "payload_required": ["origins", "destinations", "key"],
    },
}

# Map manual action types to canonical API routes.
_MANUAL_ACTION_ROUTE_MAP: dict[str, str] = {
    "cvs_refill": "POST /mock/cvs/refill",
    "pharmacy_refill": "POST /mock/cvs/refill",
    "health_refill": "POST /mock/cvs/refill",
    "appointment_booking": "POST /mock/cal/book",
    "book_appointment": "POST /mock/cal/book",
    "clinic_booking": "POST /mock/cal/book",
    "grocery_delivery": "POST /mock/instacart/cart",
    "instacart_cart": "POST /mock/instacart/cart",
    "supply_reorder": "POST /mock/amazon/order",
    "amazon_order": "POST /mock/amazon/order",
    "amazon_reorder": "POST /mock/amazon/reorder",
    "caregiver_availability": "POST /mock/caregivers/available",
    "transport": "POST /mock/caregivers/available",
}

_DOMAIN_DEFAULT_ROUTE_MAP: dict[str, str] = {
    "health": "POST /mock/cvs/refill",
    "appointment": "POST /mock/cal/book",
    "grocery": "POST /mock/instacart/cart",
}

_ALLOWED_RECIPIENT_TYPES = {
    "caregiver",
    "patient",
    "pharmacy",
    "clinic",
    "prescriber",
    "provider",
}


def _route_requires_recipient(route: str) -> bool:
    """Return True when a route requires recipient metadata on the draft."""
    return route.strip().lower() == "post resend:/emails"


def _normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def normalize_manual_action_type(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or None


def route_for_manual_action_type(manual_action_type: str | None) -> str | None:
    normalized = normalize_manual_action_type(manual_action_type)
    if not normalized:
        return None
    return _MANUAL_ACTION_ROUTE_MAP.get(normalized)


def infer_primary_route_for_action(action: dict[str, Any]) -> str | None:
    payload = action.get("api_payload")
    if isinstance(payload, dict):
        call = payload.get("call")
        if isinstance(call, dict):
            route_key = call.get("route_key")
            if isinstance(route_key, str) and route_key.strip():
                return route_key.strip()

    route = route_for_manual_action_type(action.get("manual_action_type"))
    if route:
        return route

    # Legacy fallback for historical flat payloads: infer by domain only when
    # the payload actually contains at least one of the route's required keys.
    # This prevents unrelated bookkeeping dicts from being mistaken for a call.
    domain = str(action.get("domain") or "").strip().lower()
    if isinstance(payload, dict) and payload and domain in _DOMAIN_DEFAULT_ROUTE_MAP:
        candidate = _DOMAIN_DEFAULT_ROUTE_MAP[domain]
        required = _required_payload_keys(candidate)
        if required and any(key in payload for key in required):
            return candidate
    return None


def _required_payload_keys(route: str) -> list[str]:
    schema = MOCK_ROUTE_SCHEMAS.get(route) or LIVE_ROUTE_SCHEMAS.get(route)
    if not schema:
        return []
    return list(schema.get("payload_required") or [])


def build_parameter_template(route: str) -> dict[str, dict[str, str]]:
    return {key: {"value": "<fill>"} for key in _required_payload_keys(route)}


def build_api_payload_template(route: str, provider: str | None = None) -> dict[str, Any]:
    if provider is None:
        provider = "mock" if route.startswith("POST /mock/") else "live"
    return {
        "template_version": API_PAYLOAD_TEMPLATE_VERSION,
        "call": {
            "route_key": route,
            "provider": provider,
            "parameters": build_parameter_template(route),
        },
    }


def _extract_params_from_parameter_nodes(raw_parameters: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key, value in raw_parameters.items():
        if isinstance(value, dict) and "value" in value:
            params[key] = value.get("value")
        else:
            # Compatibility: if model emits plain param values, still accept.
            params[key] = value
    return params


def resolve_route_and_params_from_action(action: dict[str, Any]) -> tuple[str | None, dict[str, Any], list[str], str]:
    """
    Resolve a call spec from action payload.

    Returns:
      route_key, params, errors, source

    source:
      - template_v1: strict template shape
      - legacy_flat_payload: historical flat payload map
      - none: no actionable route
    """
    payload = action.get("api_payload")
    route_key = infer_primary_route_for_action(action)

    if isinstance(payload, dict) and payload.get("template_version") == API_PAYLOAD_TEMPLATE_VERSION:
        call = payload.get("call")
        if not isinstance(call, dict):
            return route_key, {}, ["api_payload.call must be an object"], "template_v1"

        call_route = call.get("route_key")
        if isinstance(call_route, str) and call_route.strip():
            route_key = call_route.strip()

        raw_parameters = call.get("parameters")
        if not isinstance(raw_parameters, dict):
            return route_key, {}, ["api_payload.call.parameters must be an object"], "template_v1"

        params = _extract_params_from_parameter_nodes(raw_parameters)
        errors: list[str] = []
        for key in _required_payload_keys(route_key or ""):
            if params.get(key) in (None, "", []):
                errors.append(f"missing api_payload.call.parameters.{key}.value")
        return route_key, params, errors, "template_v1"

    if route_key and isinstance(payload, dict):
        # Legacy map where api_payload is the request body itself.
        errors: list[str] = []
        for key in _required_payload_keys(route_key):
            if payload.get(key) in (None, "", []):
                errors.append(f"missing api_payload.{key}")
        return route_key, dict(payload), errors, "legacy_flat_payload"

    return route_key, {}, [], "none"


def build_post_request_body(route: str, params: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic POST body from extracted template params."""
    required = _required_payload_keys(route)
    body: dict[str, Any] = {}
    for key in required:
        if key in params:
            body[key] = params.get(key)
    for key, value in params.items():
        if key not in body:
            body[key] = value
    return body


def enforce_action_type_exclusivity(drafts: list[Any]) -> tuple[list[Any], list[str]]:
    """Enforce mutual exclusivity of api_payload and manual_action_type.

    If a draft has both set, api_payload takes precedence and manual_action_type is cleared.
    Returns (cleaned_drafts, list_of_corrected_action_ids).
    """
    cleaned: list[Any] = []
    corrected: list[str] = []
    for draft in drafts:
        if draft.api_payload and draft.manual_action_type:
            draft = draft.copy(update={"manual_action_type": None})
            corrected.append(draft.action_id)
        cleaned.append(draft)
    return cleaned, corrected


def validate_detection_draft_for_api_requirements(
    draft: dict[str, Any],
    known_recipient_emails: set[str] | None = None,
) -> list[str]:
    """
    Validate a detection draft only when it is API-completable.

    Returns a list of validation errors. Empty list means valid (or non-API draft).
    """
    errors: list[str] = []
    route = infer_primary_route_for_action(draft)
    payload = draft.get("api_payload")
    if route:
        if not isinstance(payload, dict):
            errors.append("missing api_payload")
        else:
            if payload.get("template_version") != API_PAYLOAD_TEMPLATE_VERSION:
                errors.append("api_payload.template_version must be 'v1'")

            call = payload.get("call")
            if not isinstance(call, dict):
                errors.append("missing api_payload.call")
            else:
                route_key = call.get("route_key")
                if not route_key:
                    errors.append("missing api_payload.call.route_key")
                elif str(route_key).strip() != route:
                    errors.append(
                        f"api_payload.call.route_key must match inferred route {route!r}"
                    )

                parameters = call.get("parameters")
                if not isinstance(parameters, dict):
                    errors.append("missing api_payload.call.parameters")
                else:
                    for key in _required_payload_keys(route):
                        node = parameters.get(key)
                        if not isinstance(node, dict):
                            errors.append(f"missing api_payload.call.parameters.{key}")
                            continue
                        if node.get("value") in (None, "", []):
                            errors.append(
                                f"missing api_payload.call.parameters.{key}.value"
                            )

    recipient_email = draft.get("recipient_email")
    recipient_type = str(draft.get("recipient_type") or "").strip().lower()
    email_subject = str(draft.get("email_subject") or "").strip()
    has_email_fields = bool(recipient_email or recipient_type or email_subject)
    requires_recipient = bool(route and _route_requires_recipient(route))

    # Recipient fields are optional for most mock execution routes
    # (for example grocery cart creation). If one is provided, require
    # a complete and valid recipient tuple.
    if requires_recipient or has_email_fields:
        if not recipient_email:
            errors.append("missing recipient_email")
        if not recipient_type:
            errors.append("missing recipient_type")
        elif recipient_type not in _ALLOWED_RECIPIENT_TYPES:
            errors.append(f"invalid recipient_type={recipient_type!r}")
        if not email_subject:
            errors.append("missing email_subject")
        normalized_email = _normalize_email(recipient_email)
        if (
            normalized_email
            and known_recipient_emails is not None
            and normalized_email not in known_recipient_emails
        ):
            errors.append(f"unknown recipient_email={recipient_email!r}")

    return errors


def _template_snippet(route: str) -> str:
    return json.dumps(build_api_payload_template(route), indent=2)


def _all_post_template_catalog_lines() -> list[str]:
    routes = [
        "POST /mock/cvs/refill",
        "POST /mock/cal/book",
        "POST /mock/instacart/cart",
        "POST /mock/amazon/order",
        "POST /mock/amazon/reorder",
        "POST /mock/caregivers/available",
        "POST resend:/emails",
    ]
    lines = ["Global POST api_payload templates (reference):"]
    for route in routes:
        lines.append(f"- {route}:")
        lines.append(_template_snippet(route))
    return lines


def worker_api_capability_block(domain: str) -> str:
    """Return compact route/schema guidance for worker prompts by domain."""
    d = (domain or "").strip().lower()

    if d == "health":
        lines = [
            "API Capability Guidance (health):",
            "- GET /mock/cvs/available | when: check med availability before proposing refill (requires doctor_name)",
            "- POST /mock/cvs/refill | when: refill can be executed",
            "- Required api_payload template for refill:",
            _template_snippet("POST /mock/cvs/refill"),
            "- Fill each parameters.<field>.value; do not emit raw request-body JSON.",
            "- Live API: Resend email | include recipient_email + recipient_type + email_subject.",
        ]
    elif d == "appointment":
        lines = [
            "API Capability Guidance (appointment):",
            "- GET /mock/cal/available | when: identify open provider times before booking (requires doctor_name)",
            "- POST /mock/cal/book | when: booking can be executed",
            "- POST /mock/caregivers/available | when: transport/scheduling needs caregiver capacity",
            "- Required booking api_payload template:",
            _template_snippet("POST /mock/cal/book"),
            "- Required caregiver-capacity api_payload template:",
            _template_snippet("POST /mock/caregivers/available"),
            "- Fill each parameters.<field>.value; do not emit raw request-body JSON.",
            "- Live API: Resend email for outbound confirmations (requires email_subject).",
        ]
    elif d == "grocery":
        lines = [
            "API Capability Guidance (grocery):",
            "- POST /mock/instacart/cart | when: grocery delivery/cart can be executed",
            "- POST /mock/amazon/order (or /mock/amazon/reorder alias) | when: supply reorder can be executed",
            "- Required Instacart api_payload template:",
            _template_snippet("POST /mock/instacart/cart"),
            "- Required Amazon api_payload template:",
            _template_snippet("POST /mock/amazon/order"),
            "- Fill each parameters.<field>.value; do not emit raw request-body JSON.",
            "- Live API: Resend email for caregiver/patient notifications (requires email_subject).",
        ]
    elif d == "financial":
        lines = [
            "API Capability Guidance (financial):",
            "- Prefer non-API analytical actions unless a concrete executable route is evident.",
            "- If API-executable, emit v1 template payload with call.route_key and call.parameters.",
            "- Live API: Resend email can be used for outreach/notification tasks (requires email_subject).",
        ]
    elif d == "scheduling":
        lines = [
            "API Capability Guidance (scheduling):",
            "- POST /mock/caregivers/available | required template:",
            _template_snippet("POST /mock/caregivers/available"),
            "- GET gmaps:/maps/api/distancematrix/json (scheduling-only live API)",
            "- Use Google Maps only for travel-time enrichment in scheduling decisions.",
        ]
    else:
        lines = ["API Capability Guidance: none defined for this domain."]

    lines.extend(_all_post_template_catalog_lines())
    return "\n".join(lines)


def build_execution_plan_preview(action: dict[str, Any]) -> dict[str, Any]:
    """
    Non-mutating summary of likely approve-time calls for dashboard display.
    Mirrors api.routers.actions._build_execution_steps routing without URLs or secrets.
    """
    import os

    steps: list[dict[str, Any]] = []
    route, route_params, route_errors, route_source = resolve_route_and_params_from_action(action)
    if route and str(route).startswith("POST /mock/"):
        steps.append(
            {
                "kind": "mock_api",
                "route": route,
                "method": "POST",
                "preflight_errors": list(route_errors or []),
            }
        )

    gmaps_on = (os.getenv("ENABLE_GMAPS_ON_APPROVE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if gmaps_on:
        domain = str(action.get("domain") or "").strip().lower()
        manual = str(action.get("manual_action_type") or "").strip().lower()
        if domain == "appointment" and manual in {"transport", "caregiver_availability"}:
            api_key = os.getenv("GOOGLE_MAPS_API_KEY") or ""
            if route_params.get("origins") and route_params.get("destinations") and api_key:
                steps.append(
                    {
                        "kind": "gmaps",
                        "route": "GET gmaps:/maps/api/distancematrix/json",
                        "method": "GET",
                    }
                )

    if action.get("recipient_email"):
        steps.append({"kind": "resend", "route": "POST resend:/emails", "method": "POST"})

    return {
        "steps": steps,
        "inferred_route": route,
        "route_source": route_source,
    }
