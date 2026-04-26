"""Executor orchestrator — Sprint 2: intent-first routing with detection fan-out."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiohttp
from uagents import Agent, Context, Model, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agents.shared.config import (
    EXECUTOR_SEED,
    LocalFirstResolver,
    SCHEDULING_AGENT_ADDRESS,
    SUPERVISOR_ADDRESS_BY_DOMAIN,
)
from agents.shared.constants import AGENT_PORTS, DOMAIN_KEYWORDS, ORG_CONTEXT_MAP, SUPPORTED_DOMAINS
from agents.shared.db import (
    find_active_patients_by_name_query,
    get_org_profile,
    get_overdue_actions,
    get_patient,
    has_been_notified,
    log_expiration_notification,
    mark_action_overdue,
    serialize_complete_life_graph,
    update_action,
    write_chat_message,
    write_notification,
    write_patient,
)
from agents.shared.llm import call_claude_json
from agents.shared.models import (
    ActionDraft,
    DetectionFanOutResult,
    DomainFanOutResult,
    ExecutorErrorPayload,
    IntentClass,
    IntentRoutingResult,
    MockDomainTask,
    MockSupervisorResult,
    ModificationRequest,
    ModificationResult,
    OnDemandDetectionRequest,
    QuestionAnswer,
    QuestionRequest,
    SchedulingOptions,
    SchedulingQuery,
    SupervisorResult,
)
from agents.shared.state_service import (
    PendingFanOut,
    PendingRequest,
    fan_out_state,
    request_state,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT_SECONDS = 45.0
DETECTION_DOMAIN_TIMEOUT_SECONDS = 300.0
HEARTBEAT_INTERVAL_SECONDS = 15.0
MAILBOX_INGRESS_SILENCE_WARNING_SECONDS = 120.0

# Domains that receive detection fan-out by default (patient_create)
ALL_DETECTION_DOMAINS = ["health", "appointment", "grocery", "financial"]

# Field -> domain relevance map for patient_update pre-filter
_FIELD_DOMAIN_MAP: dict[str, list[str]] = {
    "medication": ["health"],
    "medications": ["health"],
    "drug": ["health"],
    "pharmacy": ["health"],
    "appointment": ["appointment"],
    "appointments": ["appointment"],
    "transport": ["appointment"],
    "grocery": ["grocery"],
    "food": ["grocery"],
    "diet": ["grocery"],
    "bill": ["financial"],
    "bills": ["financial"],
    "payment": ["financial"],
    "financial": ["financial"],
    "schedule": ["appointment"],
}

# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

executor = Agent(
    name="executor",
    seed=EXECUTOR_SEED,
    port=AGENT_PORTS["executor"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),
)

chat_proto = Protocol(spec=chat_protocol_spec)
_started_at = datetime.now(tz=timezone.utc)
_last_chat_ingress_at: datetime | None = None
_executor_ready: bool = False


# ---------------------------------------------------------------------------
# Models used only by executor REST layer
# ---------------------------------------------------------------------------

class HealthResponse(Model):
    status: str


class HttpMessagePost(Model):
    content: str
    action_id: str | None = None


class HttpMessageResponse(Model):
    request_id: str
    routed_domain: str
    routed_address: str
    intent: str


class InternalDetectRequest(Model):
    patient_id: str
    trigger: str  # "patient_create" | "patient_update"
    updated_domain: str | None = None


class InternalDetectResponse(Model):
    status: str
    patient_id: str
    trigger: str


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

# Keyword sets kept as sync fallback when LLM is unavailable
_QUESTION_KEYWORDS = {"what", "how", "why", "when", "where", "tell", "explain", "describe", "is there", "does"}
_MODIFICATION_KEYWORDS = {"change", "update", "modify", "edit", "revise", "adjust", "replace", "rewrite", "alter"}
_SCHEDULING_KEYWORDS = {"schedule", "availability", "slot", "caregiver", "book", "assign", "calendar"}
_DETECTION_KEYWORDS = {"check", "analyze", "analyse", "detect", "assess", "review", "scan", "patient create", "patient update"}

_INTENT_SYSTEM_PROMPT = """\
You are an intent classifier for MACOS, a multi-agent care-coordination platform.

Classify the user's natural-language query into EXACTLY ONE of these intents:

  question     – The user is asking for information about a patient, action, or
                 care topic. No data mutation is requested.

  modification – The user wants to change, revise, or update an existing action
                 draft or patient record.

  scheduling   – The user wants to arrange, book, or check availability for a
                 caregiver visit or appointment slot.

  detection    – The user wants the system to proactively analyse a patient
                 situation and surface relevant care actions. This includes
                 "run detection", "new patient", "patient added/updated", or
                 any trigger that implies a full care-gap analysis.

Also classify:

  domain       – The most relevant care domain: "health", "appointment",
                 "grocery", or "financial".
                 For detection: set the domain if the query clearly targets a
                 single domain (e.g. "health check", "medication review",
                 "missed dose", "grocery order", "bill payment"). Use null only
                 when the query implies a broad full-patient scan or new patient
                 onboarding (patient_create).
                 For scheduling: always null.

  confidence   – "high" if the intent is clear, "low" if ambiguous.

  trigger      – For detection only: "patient_create" when a new patient is
                 being added, "patient_update" when an existing patient's record
                 changed. null otherwise.

  updated_fields – For patient_update detection only: a JSON array of the field
                   names that changed (e.g. ["medications", "address"]). null
                   otherwise.

Respond with ONLY a JSON object — no prose, no markdown fences:
{
  "intent": "question|modification|scheduling|detection",
  "domain": "health|appointment|grocery|financial|null",
  "confidence": "high|low",
  "trigger": "patient_create|patient_update|null",
  "updated_fields": ["field"] or null
}
"""


async def _classify_intent_with_llm(query: str) -> IntentRoutingResult:
    """
    Primary classifier: uses Claude to parse natural language into a typed
    IntentRoutingResult. Falls back to keyword heuristics if the LLM call
    fails (no API key, parse error, or timeout).
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: call_claude_json(_INTENT_SYSTEM_PROMPT, query, max_tokens=256),
        )
        intent_str: str = raw.get("intent", "detection")
        domain_str: str | None = raw.get("domain") or None
        if domain_str == "null":
            domain_str = None
        trigger_str: str | None = raw.get("trigger") or None
        if trigger_str == "null":
            trigger_str = None
        updated_fields = raw.get("updated_fields")
        if not isinstance(updated_fields, list):
            updated_fields = None
        confidence: str = raw.get("confidence", "high")

        # Validate intent value
        valid_intents = {"question", "modification", "scheduling", "detection"}
        if intent_str not in valid_intents:
            log.warning("LLM returned unknown intent %r; falling back to keywords", intent_str)
            return _classify_intent(query)

        log.info(
            "LLM intent classification: intent=%s domain=%s confidence=%s trigger=%s",
            intent_str, domain_str, confidence, trigger_str,
        )
        return IntentRoutingResult(
            intent=intent_str,  # type: ignore[arg-type]
            domain=domain_str,
            confidence=confidence,
            trigger=trigger_str,
            updated_fields=updated_fields,
        )
    except Exception as exc:
        log.warning(
            "LLM intent classification failed (%s); falling back to keyword heuristics", exc
        )
        return _classify_intent(query)


def _classify_intent(query: str) -> IntentRoutingResult:
    """
    Keyword-based fallback classifier. Used when the LLM is unavailable.
    Also exported for use in tests (sync, no I/O).

    Precedence: scheduling > modification > question > detection (default).
    """
    lowered = query.lower()

    if any(kw in lowered for kw in _SCHEDULING_KEYWORDS):
        return IntentRoutingResult(
            intent="scheduling",
            domain=None,
            confidence="high",
            trigger=None,
            updated_fields=None,
        )

    is_detection = any(kw in lowered for kw in _DETECTION_KEYWORDS)

    if any(kw in lowered for kw in _MODIFICATION_KEYWORDS):
        return IntentRoutingResult(
            intent="modification",
            domain=_resolve_domain(lowered),
            confidence="high",
            trigger=None,
            updated_fields=None,
        )

    if any(kw in lowered for kw in _QUESTION_KEYWORDS):
        return IntentRoutingResult(
            intent="question",
            domain=_resolve_domain(lowered),
            confidence="high",
            trigger=None,
            updated_fields=None,
        )

    if is_detection:
        trigger = "patient_create" if ("create" in lowered or "new patient" in lowered) else "patient_update"
        return IntentRoutingResult(
            intent="detection",
            domain=None,
            confidence="high",
            trigger=trigger,
            updated_fields=None,
        )

    return IntentRoutingResult(
        intent="detection",
        domain=None,
        confidence="low",
        trigger="patient_update",
        updated_fields=None,
    )


def _resolve_domain(lowered: str) -> str:
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return domain
    return "health"


# Matches "pt_001", "pt_abc", "patient pt_001", etc.
_PATIENT_ID_RE = re.compile(r"\bpt_[a-zA-Z0-9]+\b", re.IGNORECASE)


def _extract_patient_id(query: str) -> str | None:
    """Pull the first patient ID (pt_XXX) from free-text, or return None."""
    match = _PATIENT_ID_RE.search(query)
    return match.group(0).lower() if match else None


def _resolve_patient_id_for_query(query: str, provided_patient_id: str | None) -> str | None:
    """
    Resolve a patient_id for question/modification routing.

    Priority:
    1. Explicitly provided patient_id.
    2. Inline pt_XXX token in query text.
    3. Name match against active patients in DB.
    Returns None if unresolvable (caller falls back to "unknown").
    """
    if provided_patient_id:
        return provided_patient_id
    extracted = _extract_patient_id(query)
    if extracted:
        return extracted
    candidates = find_active_patients_by_name_query(query)
    if len(candidates) == 1:
        return str(candidates[0]["patient_id"])
    if len(candidates) > 1:
        return str(candidates[0]["patient_id"])
    return None


def _resolve_detection_patient_id(
    query: str,
    provided_patient_id: str | None,
) -> tuple[str | None, str | None]:
    """
    Resolve detection target to a unique active patient_id.

    Resolution strategy:
    1) explicit patient_id if provided and active
    2) extract full patient name from query, then exact DB lookup by name
    """
    if provided_patient_id:
        patient = get_patient(provided_patient_id)
        if patient and int(patient.get("active") or 0) == 1:
            return provided_patient_id, None
        return None, f"Patient ID {provided_patient_id!r} is missing or inactive."

    candidates = find_active_patients_by_name_query(query)
    if len(candidates) != 1:
        if not candidates:
            return None, (
                "Detection requires a patient name in the request. "
                "No unique active patient match could be extracted."
            )
        candidate_labels = ", ".join(
            f"{item.get('name')} ({item.get('patient_id')})"
            for item in candidates[:5]
        )
        return None, (
            "Detection request is ambiguous. Multiple patient names were found: "
            + candidate_labels
        )
    return str(candidates[0]["patient_id"]), None


def _bootstrap_life_graph_snapshot(
    patient_id: str,
    query: str,
    existing_patient: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal complete life-graph envelope for patient_create bootstrap."""
    patient = existing_patient or {}
    return {
        "patient": {
            "patient_id": patient_id,
            "name": patient.get("name") or "Unknown Patient",
            "age": patient.get("age"),
            "address": patient.get("address"),
            "active": int(patient.get("active") or 1),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "preferences": patient.get("preferences_json", {}),
            "intake_summary": query[:1000] if query else "",
        },
        "assigned_caregivers": [],
        "caregiver_links": [],
        "caregivers": [],
        "caregiver_schedule": [],
        "patient_updates": [],
        "actions": [],
        "action_chat": [],
        "notifications": [],
        "expiration_notifications": [],
    }


def _resolve_patient_create_snapshot(
    query: str,
    provided_patient_id: str | None,
    pass_id: str,
) -> tuple[str, dict[str, Any], str]:
    """
    Resolve patient_create context without name matching.

    Returns:
      patient_id, full_snapshot, snapshot_source
    """
    candidate_id = provided_patient_id or _extract_patient_id(query) or f"pt_create_{pass_id[:8]}"
    existing = get_patient(candidate_id)
    db_snapshot = serialize_complete_life_graph(candidate_id)
    if db_snapshot:
        return candidate_id, db_snapshot, "executor_db_full_life_graph"
    return candidate_id, _bootstrap_life_graph_snapshot(candidate_id, query, existing), "executor_bootstrap_life_graph"


def _detection_domains_for_trigger(
    trigger: str,
    updated_fields: list[str] | None,
    domain_hint: str | None = None,
) -> list[str]:
    """
    Return the list of domains to fan out to.

    - patient_create → all domains (domain_hint ignored)
    - explicit domain_hint → single domain
    - updated_fields → field-based pre-filter
    - fallback → all domains
    """
    if trigger == "patient_create":
        return list(ALL_DETECTION_DOMAINS)
    if domain_hint and domain_hint in ALL_DETECTION_DOMAINS:
        return [domain_hint]
    if updated_fields:
        relevant: set[str] = set()
        for field in updated_fields:
            key = field.lower()
            for map_key, domains in _FIELD_DOMAIN_MAP.items():
                if map_key in key:
                    relevant.update(domains)
        if relevant:
            return list(relevant)
    return list(ALL_DETECTION_DOMAINS)


# ---------------------------------------------------------------------------
# Chat helpers
# ---------------------------------------------------------------------------

async def _send_terminal_chat_response(ctx: Context, recipient: str, text: str) -> None:
    try:
        await ctx.send(
            recipient,
            ChatMessage(
                timestamp=datetime.now(tz=timezone.utc),
                msg_id=uuid4(),
                content=[
                    TextContent(type="text", text=text),
                    EndSessionContent(type="end-session"),
                ],
            ),
        )
        ctx.logger.info("Sent terminal ChatMessage reply to recipient=%s", recipient)
    except Exception as send_err:
        ctx.logger.error(
            "Failed to send ChatMessage reply to recipient=%s: %s", recipient, send_err
        )


# ---------------------------------------------------------------------------
# Routing dispatcher (Task 3.2)
# ---------------------------------------------------------------------------

_CONVERSATIONAL_REPLY_PROMPT = """\
You are the voice of MACOS, a care-coordination assistant. The care team has just \
processed a request and you need to send a short, conversational reply back to the \
user. Write in first person as MACOS. Be warm, direct, and concise (2-4 sentences max). \
Do not use bullet points or markdown. Do not repeat the raw action IDs or technical \
field names. Focus on what was found or done and what happens next."""


async def _generate_conversational_reply(original_query: str, result_summary: str) -> str:
    """Call the LLM to turn a structured result summary into a conversational reply."""
    user_message = f"Original request: {original_query}\n\nResult summary: {result_summary}"
    try:
        raw = await asyncio.to_thread(
            call_claude_json,
            _CONVERSATIONAL_REPLY_PROMPT + '\n\nRespond with ONLY a JSON object: {"reply": "<text>"}',
            user_message,
            300,
        )
        reply = raw.get("reply") or ""
        if reply:
            return reply
    except Exception:
        pass
    return result_summary


async def _route_query(
    ctx: Context,
    query: str,
    user_sender_address: str | None,
    patient_id: str | None = None,
    intent_override: IntentRoutingResult | None = None,
    action_id: str | None = None,
) -> HttpMessageResponse:
    request_id = str(uuid4())
    intent = intent_override or await _classify_intent_with_llm(query)

    # Extract patient_id from the query text if not already supplied
    resolved_patient_id = patient_id or _extract_patient_id(query)

    ctx.logger.info(
        "Intent classified request_id=%s intent=%s domain=%s confidence=%s "
        "patient_id=%s user_sender=%s action_id=%s",
        request_id,
        intent.intent,
        intent.domain,
        intent.confidence,
        resolved_patient_id or "none",
        user_sender_address or "none",
        action_id or "none",
    )

    # --- Scheduling ---
    if intent.intent == "scheduling":
        return await _dispatch_scheduling(ctx, request_id, query, user_sender_address, intent, action_id)

    # --- Modification ---
    if intent.intent == "modification":
        return await _dispatch_modification(ctx, request_id, query, user_sender_address, intent, resolved_patient_id, action_id)

    # --- Question ---
    if intent.intent == "question":
        return await _dispatch_question(ctx, request_id, query, user_sender_address, intent, resolved_patient_id, action_id)

    # --- Detection (fan-out) ---
    return await _dispatch_detection(ctx, request_id, query, user_sender_address, intent, patient_id)


async def _dispatch_scheduling(
    ctx: Context,
    request_id: str,
    query: str,
    user_sender_address: str | None,
    intent: IntentRoutingResult,
    action_id: str | None = None,
) -> HttpMessageResponse:
    routed_address = SCHEDULING_AGENT_ADDRESS
    request_state.set_request(
        PendingRequest(
            request_id=request_id,
            query=query,
            domain="scheduling",
            intent="scheduling",
            user_sender_address=user_sender_address,
            routed_address=routed_address,
            created_at=datetime.now(tz=timezone.utc),
            action_id=action_id,
        )
    )
    task = MockDomainTask(
        request_id=request_id,
        domain="scheduling",
        query=query,
        user_sender_address=user_sender_address,
        metadata={"intent": "scheduling", "orchestrator": "executor"},
    )
    try:
        await ctx.send(routed_address, task)
    except Exception as ex:
        request_state.remove_request(request_id)
        await _handle_dispatch_error(ctx, user_sender_address, request_id, "scheduling", ex)
        raise
    return HttpMessageResponse(
        request_id=request_id,
        routed_domain="scheduling",
        routed_address=routed_address,
        intent="scheduling",
    )


async def _dispatch_modification(
    ctx: Context,
    request_id: str,
    query: str,
    user_sender_address: str | None,
    intent: IntentRoutingResult,
    patient_id: str | None,
    action_id: str | None = None,
) -> HttpMessageResponse:
    domain = intent.domain or "health"
    supervisor_address = SUPERVISOR_ADDRESS_BY_DOMAIN.get(domain, SUPERVISOR_ADDRESS_BY_DOMAIN["health"])
    resolved_pid = _resolve_patient_id_for_query(query, patient_id)
    request_state.set_request(
        PendingRequest(
            request_id=request_id,
            query=query,
            domain=domain,
            intent="modification",
            user_sender_address=user_sender_address,
            routed_address=supervisor_address,
            created_at=datetime.now(tz=timezone.utc),
            action_id=action_id,
        )
    )
    mod_request = ModificationRequest(
        action_id=request_id,
        patient_id=resolved_pid or "unknown",
        domain=domain,
        action_type="general",
        current_draft="",
        modification_instruction=query,
        life_graph_snapshot="{}",
    )
    try:
        await ctx.send(supervisor_address, mod_request)
    except Exception as ex:
        request_state.remove_request(request_id)
        await _handle_dispatch_error(ctx, user_sender_address, request_id, domain, ex)
        raise
    return HttpMessageResponse(
        request_id=request_id,
        routed_domain=domain,
        routed_address=supervisor_address,
        intent="modification",
    )


async def _dispatch_question(
    ctx: Context,
    request_id: str,
    query: str,
    user_sender_address: str | None,
    intent: IntentRoutingResult,
    patient_id: str | None,
    action_id: str | None = None,
) -> HttpMessageResponse:
    domain = intent.domain or "health"
    supervisor_address = SUPERVISOR_ADDRESS_BY_DOMAIN.get(domain, SUPERVISOR_ADDRESS_BY_DOMAIN["health"])
    resolved_pid = _resolve_patient_id_for_query(query, patient_id)
    request_state.set_request(
        PendingRequest(
            request_id=request_id,
            query=query,
            domain=domain,
            intent="question",
            user_sender_address=user_sender_address,
            routed_address=supervisor_address,
            created_at=datetime.now(tz=timezone.utc),
            action_id=action_id,
        )
    )
    q_request = QuestionRequest(
        action_id=request_id,
        patient_id=resolved_pid or "unknown",
        domain=domain,
        action_type="general",
        question=query,
        current_draft=None,
        life_graph_snapshot="{}",
    )
    try:
        await ctx.send(supervisor_address, q_request)
    except Exception as ex:
        request_state.remove_request(request_id)
        await _handle_dispatch_error(ctx, user_sender_address, request_id, domain, ex)
        raise
    return HttpMessageResponse(
        request_id=request_id,
        routed_domain=domain,
        routed_address=supervisor_address,
        intent="question",
    )


_PATIENT_EXTRACT_SYSTEM = """You are a patient intake assistant.
Extract patient information from the provided text and return a JSON object with these fields
(include only fields that are present in the text):
  patient_id (optional override), name, age, address, preferences (object with any relevant details).
You MUST return valid JSON only — no prose, no markdown fences."""


async def _extract_and_write_patient(query: str, candidate_id: str) -> str:
    """Extract patient data from query text and persist to SQLite. Returns patient_id."""
    result = await asyncio.to_thread(
        call_claude_json, _PATIENT_EXTRACT_SYSTEM, query, 1500
    )
    result["patient_id"] = candidate_id
    return write_patient(result)


async def _dispatch_detection(
    ctx: Context,
    request_id: str,
    query: str,
    user_sender_address: str | None,
    intent: IntentRoutingResult,
    patient_id: str | None,
) -> HttpMessageResponse:
    """Fan out detection requests to multiple domain supervisors in parallel (Task 3.2)."""
    pass_id = request_id
    trigger = intent.trigger or "patient_update"
    target_domains = _detection_domains_for_trigger(trigger, intent.updated_fields, domain_hint=intent.domain)
    if trigger == "patient_create":
        candidate_id = patient_id or _extract_patient_id(query) or f"pt_create_{pass_id[:8]}"
        if not get_patient(candidate_id):
            try:
                await _extract_and_write_patient(query, candidate_id)
                ctx.logger.info(
                    "[PARSE] patient_create wrote new patient to DB pass_id=%s patient_id=%s",
                    pass_id,
                    candidate_id,
                )
            except Exception as exc:
                ctx.logger.warning(
                    "[PARSE] patient_create extraction failed, proceeding with bootstrap pass_id=%s err=%s",
                    pass_id,
                    exc,
                )
        pid, full_snapshot, snapshot_source = _resolve_patient_create_snapshot(
            query=query,
            provided_patient_id=candidate_id,
            pass_id=pass_id,
        )
        ctx.logger.info(
            "[PARSE] patient_create bypassed name resolution pass_id=%s patient_id=%s source=%s",
            pass_id,
            pid,
            snapshot_source,
        )
    else:
        pid, resolution_error = _resolve_detection_patient_id(query, patient_id)
        if resolution_error or not pid:
            message = resolution_error or "Failed to resolve detection patient."
            ctx.logger.error(
                "[VALIDATE] Detection blocked pass_id=%s trigger=%s reason=%r query=%r",
                pass_id,
                trigger,
                message,
                query[:200],
            )
            if user_sender_address:
                await _send_terminal_chat_response(ctx, user_sender_address, message)
            return HttpMessageResponse(
                request_id=request_id,
                routed_domain="detection",
                routed_address="validation_error",
                intent="detection",
            )

        full_snapshot = serialize_complete_life_graph(pid)
        if not full_snapshot:
            message = f"No life graph found for patient_id={pid!r}; detection aborted."
            ctx.logger.error(
                "[VALIDATE] Detection blocked pass_id=%s patient_id=%s reason=%r",
                pass_id,
                pid,
                message,
            )
            if user_sender_address:
                await _send_terminal_chat_response(ctx, user_sender_address, message)
            return HttpMessageResponse(
                request_id=request_id,
                routed_domain="detection",
                routed_address="snapshot_error",
                intent="detection",
            )
        snapshot_source = "executor_db_full_life_graph"

    snapshot_meta = {
        "source": snapshot_source,
        "snapshot_version": "v1",
        "snapshot_generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "snapshot_top_level_keys": sorted(list(full_snapshot.keys())),
        "snapshot_size_bytes": len(json.dumps(full_snapshot, default=str)),
    }

    ctx.logger.info(
        "[RECV] Detection fan-out pass_id=%s patient_id=%s trigger=%s domains=%s "
        "snapshot_keys=%s snapshot_bytes=%s",
        pass_id,
        pid,
        trigger,
        target_domains,
        snapshot_meta["snapshot_top_level_keys"],
        snapshot_meta["snapshot_size_bytes"],
    )

    # Register the fan-out in state before sending any messages
    fan_out = PendingFanOut(
        pass_id=pass_id,
        patient_id=pid,
        user_sender_address=user_sender_address,
        target_domains=target_domains,
        original_query=query,
    )
    fan_out_state.register(fan_out)

    # Also register in normal request_state for timeout sweep
    request_state.set_request(
        PendingRequest(
            request_id=request_id,
            query=query,
            domain="detection",
            intent="detection",
            user_sender_address=user_sender_address,
            routed_address=",".join(target_domains),
            created_at=datetime.now(tz=timezone.utc),
        )
    )

    org = get_org_profile()
    failed_domains: list[str] = []
    for domain in target_domains:
        supervisor_address = SUPERVISOR_ADDRESS_BY_DOMAIN.get(domain)
        if not supervisor_address:
            ctx.logger.warning("No supervisor address for domain=%s, skipping", domain)
            fan_out.record_timeout(domain)
            failed_domains.append(domain)
            continue
        detection_msg = OnDemandDetectionRequest(
            patient_id=pid,
            trigger=trigger,
            pass_id=pass_id,
            updated_domain=None,
            org_context={k: org.get(k) for k in ORG_CONTEXT_MAP.get(domain, [])},
            patient_snapshot=full_snapshot,
            snapshot_meta=snapshot_meta,
            domain_patient_context=None,
        )
        try:
            ctx.logger.info(
                "[ROUTE] Detection pass_id=%s patient_id=%s -> domain=%s addr=%s",
                pass_id,
                pid,
                domain,
                supervisor_address,
            )
            await ctx.send(supervisor_address, detection_msg)
            ctx.logger.info(
                "[SEND] Detection pass_id=%s domain=%s address=%s",
                pass_id,
                domain,
                supervisor_address,
            )
        except Exception as ex:
            ctx.logger.error(
                "Failed to dispatch detection to domain=%s: %s", domain, ex
            )
            fan_out.record_timeout(domain)
            failed_domains.append(domain)

    if failed_domains:
        ctx.logger.warning(
            "Detection fan-out pass_id=%s: %d/%d domains failed dispatch: %s",
            pass_id,
            len(failed_domains),
            len(target_domains),
            failed_domains,
        )

    return HttpMessageResponse(
        request_id=request_id,
        routed_domain="detection",
        routed_address=",".join(target_domains),
        intent="detection",
    )


async def _handle_dispatch_error(
    ctx: Context,
    user_sender_address: str | None,
    request_id: str,
    domain: str,
    exc: Exception,
) -> None:
    ctx.logger.exception(
        "Dispatch error request_id=%s domain=%s: %s", request_id, domain, exc
    )
    if user_sender_address:
        await _send_terminal_chat_response(
            ctx,
            user_sender_address,
            f"Sorry, I could not route your request to the {domain} domain. Please try again.",
        )


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@executor.on_rest_get("/health", HealthResponse)
async def health(_: Context) -> HealthResponse:
    return HealthResponse(status="ok healthy")


@executor.on_rest_post("/message", HttpMessagePost, HttpMessageResponse)
async def post_message(ctx: Context, req: HttpMessagePost) -> HttpMessageResponse:
    ctx.logger.info("Received REST /message content=%r", req.content)
    return await _route_query(ctx, req.content, user_sender_address=None, action_id=req.action_id)


@executor.on_rest_post("/internal/detect", InternalDetectRequest, InternalDetectResponse)
async def internal_detect(ctx: Context, req: InternalDetectRequest) -> InternalDetectResponse:
    """Internal trigger: run detection for a specific patient without a chat message."""
    if not _executor_ready:
        ctx.logger.error(
            "POST /internal/detect received but executor event loop is not ready — "
            "agent startup has not completed; request rejected"
        )
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Executor event loop not ready; retry after agent startup completes")
    ctx.logger.info(
        "POST /internal/detect patient_id=%s trigger=%s updated_domain=%s",
        req.patient_id,
        req.trigger,
        req.updated_domain,
    )
    updated_fields = [req.updated_domain] if req.updated_domain else None
    intent = IntentRoutingResult(
        intent="detection",
        domain=None,
        confidence="high",
        trigger=req.trigger,
        updated_fields=updated_fields,
    )
    await _dispatch_detection(
        ctx,
        request_id=str(uuid4()),
        query=f"internal detect {req.patient_id}",
        user_sender_address=None,
        intent=intent,
        patient_id=req.patient_id,
    )
    return InternalDetectResponse(status="triggered", patient_id=req.patient_id, trigger=req.trigger)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@executor.on_event("startup")
async def log_startup_health(ctx: Context) -> None:
    global _executor_ready
    _executor_ready = True
    mailbox_client_present = executor.mailbox_client is not None
    agentverse_url = executor._agentverse.url if hasattr(executor, "_agentverse") else "unknown"
    mailbox_poll_url = (
        f"{executor._agentverse.agents_api}/{executor.address}/mailbox"
        if mailbox_client_present
        else "N/A"
    )
    ctx.logger.info(
        "Executor startup ready address=%s mailbox_client=%s agentverse=%s poll_url=%s",
        executor.address,
        "present" if mailbox_client_present else "MISSING",
        agentverse_url,
        mailbox_poll_url,
    )
    if not mailbox_client_present:
        ctx.logger.warning(
            "Mailbox client not initialized. ASI:One messages will not be received."
        )


# ---------------------------------------------------------------------------
# Chat protocol handlers (Task 3.3 — preserve mailbox boundary)
# ---------------------------------------------------------------------------

@chat_proto.on_message(ChatMessage, allow_unverified=True)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    global _last_chat_ingress_at
    _last_chat_ingress_at = datetime.now(tz=timezone.utc)
    ctx.logger.info(
        "Received ChatMessage sender=%s msg_id=%s", sender, msg.msg_id
    )

    # Immediate acknowledgement (Sprint 1 invariant preserved)
    try:
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(tz=timezone.utc),
                acknowledged_msg_id=msg.msg_id,
            ),
        )
    except Exception as ack_err:
        ctx.logger.warning("ChatAcknowledgement failed (non-fatal): %s", ack_err)

    text_parts = [item.text for item in msg.content if isinstance(item, TextContent)]
    text = " ".join(text_parts).strip()
    ctx.logger.info("Parsed ChatMessage sender=%s text=%r", sender, text)

    if not text:
        ctx.logger.info("Empty ChatMessage from sender=%s (session init?), skipping", sender)
        return

    # Immediate processing feedback
    try:
        await ctx.send(
            sender,
            ChatMessage(
                timestamp=datetime.now(tz=timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text="Processing your request…")],
            ),
        )
    except Exception:
        pass

    await _route_query(ctx, text, user_sender_address=sender)


@chat_proto.on_message(ChatAcknowledgement, allow_unverified=True)
async def handle_chat_ack(_: Context, __: str, ___: ChatAcknowledgement) -> None:
    return


# ---------------------------------------------------------------------------
# Production result handlers
# ---------------------------------------------------------------------------

@executor.on_message(MockSupervisorResult)
async def handle_mock_supervisor_result(
    ctx: Context, sender: str, result: MockSupervisorResult
) -> None:
    """Backward-compatible mock result handler (still used by scheduling agent)."""
    pending = request_state.remove_request(result.request_id)
    ctx.logger.info(
        "MockSupervisorResult sender=%s request_id=%s domain=%s",
        sender,
        result.request_id,
        result.domain,
    )
    if pending is None:
        ctx.logger.warning("No pending state for request_id=%s", result.request_id)
        return
    summary = f"Scheduling result ({result.domain}): {result.result}"
    final_text = await _generate_conversational_reply(pending.query, summary)
    if pending.action_id:
        write_chat_message(pending.action_id, "assistant", final_text, intent="scheduling")
        ctx.logger.info("Wrote assistant reply to action_chat action_id=%s", pending.action_id)
    if pending.user_sender_address:
        await _send_terminal_chat_response(ctx, pending.user_sender_address, final_text)


@executor.on_message(SupervisorResult)
async def handle_supervisor_detection_result(
    ctx: Context, sender: str, result: SupervisorResult
) -> None:
    """Handle production detection result from a domain supervisor."""
    ctx.logger.info(
        "SupervisorResult sender=%s pass_id=%s domain=%s actions=%d",
        sender,
        result.pass_id,
        result.domain,
        len(result.actions),
    )
    fan_out = fan_out_state.get(result.pass_id)
    if fan_out is None:
        ctx.logger.warning(
            "No active fan-out for pass_id=%s (domain=%s)", result.pass_id, result.domain
        )
        return

    fan_out.record_result(
        result.domain,
        {"actions": [a.dict() for a in result.actions], "domain": result.domain},
    )
    ctx.logger.info(
        "Fan-out pass_id=%s domain=%s recorded. Pending: %s",
        result.pass_id,
        result.domain,
        fan_out.pending_domains(),
    )

    for action in result.actions:
        if action.type == "scheduling_task":
            update_action(action.action_id, {"scheduling_status": "pending_approval"})
            ctx.logger.info(
                "scheduling_status=pending_approval set action_id=%s", action.action_id
            )

    if fan_out.is_complete():
        await _finalize_detection_fan_out(ctx, fan_out)


@executor.on_message(QuestionAnswer)
async def handle_question_answer(
    ctx: Context, sender: str, answer: QuestionAnswer
) -> None:
    """Handle production question answer from domain supervisor."""
    pending = request_state.remove_request(answer.action_id)
    ctx.logger.info(
        "QuestionAnswer sender=%s action_id=%s requires_action=%s",
        sender,
        answer.action_id,
        answer.requires_action,
    )
    if pending is None:
        ctx.logger.warning("No pending state for action_id=%s", answer.action_id)
        return
    raw_answer = answer.answer
    if answer.requires_action and answer.suggested_action:
        raw_answer += f" Suggested next step: {answer.suggested_action}"
    response_text = await _generate_conversational_reply(pending.query, raw_answer)
    if pending.action_id:
        write_chat_message(pending.action_id, "assistant", response_text, intent="question")
        ctx.logger.info("Wrote assistant reply to action_chat action_id=%s", pending.action_id)
    if pending.user_sender_address:
        await _send_terminal_chat_response(ctx, pending.user_sender_address, response_text)


@executor.on_message(ModificationResult)
async def handle_modification_result(
    ctx: Context, sender: str, result: ModificationResult
) -> None:
    """Handle production modification result from domain supervisor."""
    pending = request_state.remove_request(result.action_id)
    ctx.logger.info(
        "ModificationResult sender=%s action_id=%s patient_id=%s",
        sender,
        result.action_id,
        result.patient_id,
    )
    if pending is None:
        ctx.logger.warning("No pending state for action_id=%s", result.action_id)
        return
    summary = f"Changes made: {result.changes_summary}. Updated draft: {result.revised_draft}"
    response_text = await _generate_conversational_reply(pending.query, summary)
    if pending.action_id:
        write_chat_message(pending.action_id, "assistant", response_text, intent="modification")
        ctx.logger.info("Wrote assistant reply to action_chat action_id=%s", pending.action_id)
    if pending.user_sender_address:
        await _send_terminal_chat_response(ctx, pending.user_sender_address, response_text)


async def _finalize_detection_fan_out(ctx: Context, fan_out: PendingFanOut) -> None:
    """Build and deliver aggregated detection result to the originating sender."""
    fan_out_state.remove(fan_out.pass_id)
    request_state.remove_request(fan_out.pass_id)

    domain_results: list[DomainFanOutResult] = []
    total_actions = 0
    for domain in fan_out.target_domains:
        result = fan_out.domain_results.get(domain)
        timed_out = fan_out.domain_timeouts.get(domain, False)
        if result is None:
            domain_results.append(
                DomainFanOutResult(
                    domain=domain,
                    success=False,
                    actions=[],
                    error="timed_out" if timed_out else "no_response",
                    timed_out=timed_out,
                )
            )
        else:
            actions = result.get("actions", [])
            total_actions += len(actions)
            domain_results.append(
                DomainFanOutResult(
                    domain=domain,
                    success=True,
                    actions=actions,
                    error=None,
                    timed_out=False,
                )
            )

    partial = any(not dr.success for dr in domain_results)
    ctx.logger.info(
        "Detection fan-out complete pass_id=%s total_actions=%d partial=%s",
        fan_out.pass_id,
        total_actions,
        partial,
    )

    if fan_out.user_sender_address:
        patient_row = get_patient(fan_out.patient_id)
        patient_name = (patient_row.get("name") if patient_row else None) or fan_out.patient_id
        successful = [dr for dr in domain_results if dr.success]
        failed = [dr.domain for dr in domain_results if not dr.success]

        summary_parts = [f"Patient: {patient_name}. Found {total_actions} proposed action(s)."]
        for dr in successful:
            descs = [a.get("description") or a.get("type") or "action" for a in dr.actions]
            summary_parts.append(f"{dr.domain.capitalize()}: {'; '.join(descs[:3])}{'...' if len(descs) > 3 else ''}.")
        if failed:
            summary_parts.append(f"No response from: {', '.join(failed)}.")

        reply = await _generate_conversational_reply(
            fan_out.original_query, " ".join(summary_parts)
        )
        await _send_terminal_chat_response(ctx, fan_out.user_sender_address, reply)


# ---------------------------------------------------------------------------
# Heartbeat and timeout sweep (Task 3.4 — structured error mapping)
# ---------------------------------------------------------------------------

@executor.on_interval(period=HEARTBEAT_INTERVAL_SECONDS)
async def heartbeat_and_timeout_sweep(ctx: Context) -> None:
    # Sweep stale single-domain requests
    stale_requests = request_state.remove_stale_requests(REQUEST_TIMEOUT_SECONDS)
    for pending in stale_requests:
        age_seconds = (datetime.now(tz=timezone.utc) - pending.created_at).total_seconds()
        ctx.logger.warning(
            "Request timeout request_id=%s domain=%s intent=%s age_sec=%.1f",
            pending.request_id,
            pending.domain,
            pending.intent,
            age_seconds,
        )
        if pending.user_sender_address:
            await _send_terminal_chat_response(
                ctx,
                pending.user_sender_address,
                f"Sorry, your {pending.intent} request timed out. Please try again.",
            )

    # Sweep stale fan-outs (use detection timeout budget)
    stale_fan_outs = fan_out_state.remove_stale(DETECTION_DOMAIN_TIMEOUT_SECONDS)
    for fo in stale_fan_outs:
        ctx.logger.warning(
            "Fan-out timeout pass_id=%s patient_id=%s pending=%s age_sec=%.1f",
            fo.pass_id,
            fo.patient_id,
            fo.pending_domains(),
            fo.age_seconds(),
        )
        # Mark pending domains as timed out and finalize with partial results
        for domain in fo.pending_domains():
            fo.record_timeout(domain)
        await _finalize_detection_fan_out(ctx, fo)

    # Log heartbeat metrics
    pending_snapshot = request_state.all_requests()
    pending_count = len(pending_snapshot)
    oldest_pending_age_seconds = 0.0
    if pending_count:
        oldest_created_at = min(p.created_at for p in pending_snapshot.values())
        oldest_pending_age_seconds = (
            datetime.now(tz=timezone.utc) - oldest_created_at
        ).total_seconds()
    chat_ingress_age_seconds = (
        (datetime.now(tz=timezone.utc) - _last_chat_ingress_at).total_seconds()
        if _last_chat_ingress_at
        else (datetime.now(tz=timezone.utc) - _started_at).total_seconds()
    )
    ctx.logger.info(
        "Heartbeat pending_requests=%s oldest_pending_age_sec=%.1f chat_ingress_age_sec=%.1f",
        pending_count,
        oldest_pending_age_seconds,
        chat_ingress_age_seconds,
    )
    if pending_count > 0 and chat_ingress_age_seconds >= MAILBOX_INGRESS_SILENCE_WARNING_SECONDS:
        ctx.logger.warning(
            "Potential mailbox ingress stall: pending_requests=%s oldest_pending_age_sec=%.1f no_chat_ingress_sec=%.1f",
            pending_count,
            oldest_pending_age_seconds,
            chat_ingress_age_seconds,
        )


# ---------------------------------------------------------------------------
# Expiration loop
# ---------------------------------------------------------------------------

@executor.on_interval(period=900.0)
async def expiration_check(ctx: Context) -> None:
    """Mark overdue actions and emit deduped notifications for dashboard + asi_one channels."""
    overdue = get_overdue_actions()
    if not overdue:
        return
    ctx.logger.info("Expiration check: %d overdue action(s) found", len(overdue))
    for action in overdue:
        action_id = action["action_id"]
        patient_id = action.get("patient_id", "")
        mark_action_overdue(action_id)
        for channel in ("dashboard", "asi_one"):
            if has_been_notified(action_id, channel):
                continue
            if channel == "dashboard":
                write_notification(
                    type="overdue",
                    action_id=action_id,
                    patient_id=patient_id,
                    title=f"Overdue: {action.get('type', 'task')} for patient {patient_id}",
                    body=action.get("description", "Action review deadline has passed"),
                )
            log_expiration_notification(action_id, channel)
            ctx.logger.info(
                "Expiration notification logged action_id=%s channel=%s", action_id, channel
            )


# ---------------------------------------------------------------------------
# Mailbox diagnostics (preserved from Sprint 1)
# ---------------------------------------------------------------------------

class MailboxDebugResponse(Model):
    address: str
    poll_url: str
    http_status: int
    item_count: int
    items_preview: list[str]
    error: str | None


async def _raw_mailbox_poll(ctx: Context) -> MailboxDebugResponse:
    if executor.mailbox_client is None:
        return MailboxDebugResponse(
            address=executor.address,
            poll_url="N/A",
            http_status=-1,
            item_count=0,
            items_preview=[],
            error="mailbox_client is None",
        )
    agents_url = executor._agentverse.agents_api
    poll_url = f"{agents_url}/{executor.address}/mailbox"
    try:
        attestation = executor.mailbox_client.attestation
        async with aiohttp.ClientSession() as session:
            async with session.get(
                poll_url,
                headers={"Authorization": f"Agent {attestation}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                status = resp.status
                if status == 200:
                    items = await resp.json()
                    return MailboxDebugResponse(
                        address=executor.address,
                        poll_url=poll_url,
                        http_status=status,
                        item_count=len(items),
                        items_preview=[str(it)[:120] for it in items[:5]],
                        error=None,
                    )
                body = await resp.text()
                return MailboxDebugResponse(
                    address=executor.address,
                    poll_url=poll_url,
                    http_status=status,
                    item_count=0,
                    items_preview=[],
                    error=body[:300],
                )
    except Exception as exc:
        return MailboxDebugResponse(
            address=executor.address,
            poll_url=poll_url,
            http_status=-1,
            item_count=0,
            items_preview=[],
            error=str(exc)[:300],
        )


@executor.on_rest_get("/mailbox-debug", MailboxDebugResponse)
async def mailbox_debug(ctx: Context) -> MailboxDebugResponse:
    result = await _raw_mailbox_poll(ctx)
    ctx.logger.info(
        "MAILBOX-DEBUG poll: status=%s items=%s error=%s",
        result.http_status,
        result.item_count,
        result.error,
    )
    return result


@executor.on_interval(period=20.0)
async def mailbox_diagnostic_poll(ctx: Context) -> None:
    result = await _raw_mailbox_poll(ctx)
    ctx.logger.info(
        "MAILBOX-DIAG poll_url=%s status=%s items=%s error=%s",
        result.poll_url,
        result.http_status,
        result.item_count,
        result.error,
    )
    if result.item_count > 0:
        for i, preview in enumerate(result.items_preview):
            ctx.logger.info("MAILBOX-DIAG item[%d]: %s", i, preview)


# ---------------------------------------------------------------------------
# Protocol registration
# ---------------------------------------------------------------------------

executor.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    executor.run()
