"""Executor orchestrator — Sprint 2: intent-first routing with detection fan-out."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
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
    ASI_ONE_AGENT_ADDRESS,
    EXECUTOR_SEED,
    LocalFirstResolver,
    SUPERVISOR_ADDRESS_BY_DOMAIN,
)
from agents.shared.constants import AGENT_PORTS, DOMAIN_KEYWORDS, ORG_CONTEXT_MAP, SUPPORTED_DOMAINS
from agents.shared.db import (
    find_active_patients_by_name_query,
    get_action,
    get_action_rankings,
    get_all_patients,
    get_org_profile,
    get_overdue_actions,
    get_patient,
    get_pending_actions,
    has_been_notified,
    log_expiration_notification,
    mark_action_overdue,
    serialize_complete_life_graph,
    update_action,
    write_chat_message,
    write_notification,
    write_patient,
    write_staged_action,
)
from agents.shared.llm import call_claude, call_claude_json
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


class InternalExpirationCheckRequest(Model):
    force_overdue: bool = False
    action_id: str | None = None


class InternalExpirationCheckResponse(Model):
    status: str
    forced_action_id: str | None = None
    overdue_found: int = 0
    alerts_sent_dashboard: int = 0
    alerts_sent_asi_one: int = 0


class GeneralChatMessage(Model):
    id: int | None = None
    role: str
    content: str
    stage: str = ""
    intent_class: str | None = None
    domain: str | None = None
    patient_ids: list[str] | None = None
    draft_action_id: str | None = None
    created_at: str | None = None


class GeneralChatRequest(Model):
    session_id: str
    messages: list[GeneralChatMessage]


class GeneralChatResponse(Model):
    reply: str
    stage: str
    draft_action_id: str | None = None
    intent_class: str | None = None
    domain: str | None = None
    patient_ids: list[str] | None = None


class ReviseRequest(Model):
    original_draft: dict[str, Any]
    feedback: str
    session_id: str


class ReviseResponse(Model):
    revised_draft: dict[str, Any] | None = None
    reply: str


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

# Keyword sets kept as sync fallback when LLM is unavailable
_QUESTION_KEYWORDS = {"what", "how", "why", "when", "where", "tell", "explain", "describe", "is there", "does"}
_MODIFICATION_KEYWORDS = {"change", "update", "modify", "edit", "revise", "adjust", "replace", "rewrite", "alter"}
_DETECTION_KEYWORDS = {"check", "analyze", "analyse", "detect", "assess", "review", "scan", "patient create", "patient update"}

_INTENT_SYSTEM_PROMPT = """\
You are an intent classifier for MACOS, a multi-agent care-coordination platform.

Classify the user's natural-language query into EXACTLY ONE of these intents:

  question     – The user is asking for information about a patient, action, or
                 care topic. No data mutation is requested.

  modification – The user wants to change, revise, or update an existing action
                 draft or patient record.

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

  confidence   – "high" if the intent is clear, "low" if ambiguous.

  trigger      – For detection only: "patient_create" when a new patient is
                 being added, "patient_update" when an existing patient's record
                 changed. null otherwise.

  updated_fields – For patient_update detection only: a JSON array of the field
                   names that changed (e.g. ["medications", "address"]). null
                   otherwise.

Respond with ONLY a JSON object — no prose, no markdown fences:
{
  "intent": "question|modification|detection",
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
        valid_intents = {"question", "modification", "detection"}
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

    Precedence: modification > question > detection (default).
    """
    lowered = query.lower()

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

    # --- Onboarding: no patient context and no action context ---
    if not resolved_patient_id and not action_id and intent.intent not in ("detection", "question", "modification"):
        onboarding_reply = (
            "Welcome! To add a new patient, please provide:\n"
            "1. Patient name and date of birth\n"
            "2. Address\n"
            "3. Primary care physician name\n"
            "4. Current medications (if any)\n\n"
            "You can say something like: 'Add patient John Smith, 75 years old, at 123 Main St, "
            "doctor Dr. Jones, taking Lisinopril 10mg daily.'"
        )
        if user_sender_address:
            await _send_terminal_chat_response(ctx, user_sender_address, onboarding_reply)
        return HttpMessageResponse(
            request_id=request_id,
            routed_domain="onboarding",
            routed_address="onboarding",
            intent="onboarding",
        )

    # --- Modification ---
    if intent.intent == "modification":
        return await _dispatch_modification(ctx, request_id, query, user_sender_address, intent, resolved_patient_id, action_id)

    # --- Question ---
    if intent.intent == "question":
        return await _dispatch_question(ctx, request_id, query, user_sender_address, intent, resolved_patient_id, action_id)

    # --- General query fallback ---
    if intent.intent == "general" or (intent.intent not in ("modification", "question", "detection")):
        return await _dispatch_general_query(ctx, request_id, query, user_sender_address, intent, resolved_patient_id)

    # --- Detection (fan-out) ---
    return await _dispatch_detection(ctx, request_id, query, user_sender_address, intent, patient_id)


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
    current_draft = ""
    action_type = "general"
    if action_id:
        action_record = await asyncio.to_thread(get_action, action_id)
        if action_record:
            current_draft = action_record.get("draft_content") or action_record.get("description") or ""
            action_type = action_record.get("type") or "general"
            if not resolved_pid or resolved_pid == "unknown":
                resolved_pid = action_record.get("patient_id", resolved_pid)

    mod_request = ModificationRequest(
        action_id=action_id or request_id,
        patient_id=resolved_pid or "unknown",
        domain=domain,
        action_type=action_type,
        current_draft=current_draft,
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
    current_draft = None
    if action_id:
        action_record = await asyncio.to_thread(get_action, action_id)
        if action_record:
            current_draft = action_record.get("draft_content") or action_record.get("description")
            if not resolved_pid or resolved_pid == "unknown":
                resolved_pid = action_record.get("patient_id", resolved_pid)

    q_request = QuestionRequest(
        action_id=request_id,
        patient_id=resolved_pid or "unknown",
        domain=domain,
        action_type="general",
        question=query,
        current_draft=current_draft,
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


async def _dispatch_general_query(
    ctx: Context,
    request_id: str,
    query: str,
    user_sender_address: str | None,
    intent: IntentRoutingResult,
    patient_id: str | None,
) -> HttpMessageResponse:
    """Fallback: fetch patient life graph and answer directly via LLM."""
    pid = patient_id or _resolve_patient_id_for_query(query, patient_id)
    life_graph: dict = {}
    if pid:
        try:
            life_graph = await asyncio.to_thread(serialize_complete_life_graph, pid) or {}
        except Exception as exc:
            ctx.logger.warning("[GENERAL-FALLBACK] life graph fetch failed: %s", exc)

    system_prompt = (
        "You are a care operations assistant. Answer the caregiver's question using the provided patient context. "
        "Be concise and clinically accurate. If context is missing, say so clearly."
    )
    user_prompt = f"Question: {query}\n\nPatient context:\n{json.dumps(life_graph, indent=2)}"

    try:
        answer = await asyncio.to_thread(call_claude, system_prompt, user_prompt, 800)
    except Exception as exc:
        answer = f"Unable to answer: {exc}"

    if user_sender_address:
        await _send_terminal_chat_response(ctx, user_sender_address, answer)

    return HttpMessageResponse(
        request_id=request_id,
        routed_domain="general",
        routed_address="llm_fallback",
        intent="general",
    )


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

# ---------------------------------------------------------------------------
# General-chat pipeline
# ---------------------------------------------------------------------------

_GENERAL_CHAT_CLASSIFY_PROMPT = """\
You are an intent classifier for MACOS, a care-coordination assistant.

Classify the final user message in the conversation into ONE of:
  question     – the user wants information (no new action needed)
  create-action – the user wants to initiate a new care action or task

Also extract:
  domain – the most relevant care domain: "health", "appointment", "grocery", or "financial"
           (use your best judgement from context; default to "health" if unclear)
  confidence – "high" or "low"
  needs_db_query – true if the question can be answered from structured records (actions,
                   schedules, patient profiles, task lists, urgency/priority, overdue status)
                   WITHOUT requiring clinical or domain-specific expertise.
                   false if the question needs domain knowledge (e.g. medication interactions,
                   clinical assessment, dietary advice, financial planning advice).
                   Always true for questions about: pending/unresolved actions, urgent tasks,
                   overdue items, patient summaries, schedules, or anything phrased as
                   "what does X have", "what is outstanding", "what needs to be done".
                   Only false for: "is this medication safe?", "what diet is best for X?", etc.

Respond with ONLY valid JSON, no prose:
{
  "intent": "question|create-action",
  "domain": "health|appointment|grocery|financial",
  "confidence": "high|low",
  "needs_db_query": true|false
}
"""

_PATIENT_RESOLVE_PROMPT = """\
You are a patient name extractor for MACOS.
Given the conversation, extract the full name(s) of any patients mentioned.
Return ONLY a JSON object: {"names": ["Full Name 1", "Full Name 2"]}
If no patient name is clearly mentioned, return {"names": []}.
"""

_CLARIFY_PROMPT = """\
You are MACOS, a care-coordination assistant. Based on the conversation, you have classified:
- Intent: {intent}
- Domain: {domain}
- Patients: {patients}

Write a SHORT, warm clarification message to the caregiver (2-3 sentences) confirming your understanding:
"I understand you want to [intent summary] in the [domain] domain for [patient name(s)].
Is that correct? Feel free to correct me if I got anything wrong."

Respond with ONLY a JSON object: {"reply": "<text>"}
"""

_CONFIRM_CHECK_PROMPT = """\
You are checking whether the caregiver has confirmed or is correcting your assumptions.
The caregiver said: "{message}"

Respond with ONLY a JSON object:
{
  "confirmed": true | false,
  "correction": "<what the caregiver wants to change, or null if confirmed>"
}
If the message is an affirmative (yes, correct, that's right, ok, sure, go ahead, yep), set confirmed=true.
"""

_CREATE_ACTION_PROMPT = """\
You are a care action generator for MACOS.
Generate a draft action based on this request.

Domain: {domain}
Patient: {patient_name} ({patient_id})
Request: {request}

Produce a JSON object for the action with these fields:
{{
  "patient_id": "{patient_id}",
  "domain": "{domain}",
  "type": "<short action type, e.g. 'appointment', 'medication_refill', 'grocery_order'>",
  "description": "<concise description of the action, 1-2 sentences>",
  "draft_content": "<detailed draft content for the caregiver>",
  "urgency_level": "tier_1|tier_2|tier_3",
  "review_by": "<ISO date string, e.g. 2026-05-03>",
  "manual_action_type": "<null or short label if manual step required>"
}}
Return ONLY the JSON object.
"""

_REVISE_ACTION_PROMPT = """\
You are a care action reviser for MACOS.
You have an existing draft action and caregiver feedback. Produce a revised action.

Original draft:
{original_draft}

Caregiver feedback: "{feedback}"

Return a revised JSON object with the same fields as the original, incorporating the feedback.
Return ONLY the JSON object.
"""


def _last_user_message(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _conversation_text(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"{role.upper()}: {content}")
    return "\n".join(parts)


async def _classify_general_chat_intent(messages: list[dict]) -> dict:
    conv = _conversation_text(messages)
    try:
        raw = await asyncio.to_thread(
            call_claude_json, _GENERAL_CHAT_CLASSIFY_PROMPT, conv, 256
        )
        if raw.get("intent") in ("question", "create-action"):
            return raw
    except Exception:
        pass
    last = _last_user_message(messages).lower()
    intent = "create-action" if any(
        kw in last for kw in ["schedule", "create", "add", "set up", "book", "arrange", "order", "need to"]
    ) else "question"
    return {"intent": intent, "domain": _resolve_domain(last), "confidence": "low"}


async def _extract_patient_names(messages: list[dict]) -> list[str]:
    conv = _conversation_text(messages[-4:])  # last 4 messages for efficiency
    try:
        raw = await asyncio.to_thread(call_claude_json, _PATIENT_RESOLVE_PROMPT, conv, 256)
        names = raw.get("names") or []
        return [n for n in names if isinstance(n, str) and n.strip()]
    except Exception:
        return []


async def _resolve_patients_from_names(names: list[str]) -> list[dict]:
    resolved = []
    for name in names:
        candidates = await asyncio.to_thread(find_active_patients_by_name_query, name)
        if candidates:
            p = candidates[0]
            resolved.append({"id": p["patient_id"], "name": p["name"]})
    return resolved


def _is_in_clarification(messages: list[dict]) -> bool:
    """True if the last agent message had stage='clarifying'."""
    for m in reversed(messages):
        if m.get("role") == "agent":
            return m.get("stage") == "clarifying"
    return False


def _get_clarification_context(messages: list[dict]) -> tuple[str, str, list[dict]]:
    """Extract the last known intent/domain/patients from agent messages."""
    for m in reversed(messages):
        if m.get("role") == "agent" and m.get("stage") == "clarifying":
            return (
                m.get("intent_class") or "create-action",
                m.get("domain") or "health",
                [{"id": pid, "name": pid} for pid in (m.get("patient_ids") or [])],
            )
    return "create-action", "health", []


async def _check_caregiver_confirmed(last_message: str) -> dict:
    try:
        raw = await asyncio.to_thread(
            call_claude_json,
            _CONFIRM_CHECK_PROMPT.format(message=last_message),
            last_message,
            200,
        )
        return raw
    except Exception:
        affirmatives = {"yes", "correct", "ok", "sure", "go ahead", "yep", "that's right", "yeah", "right", "confirm"}
        if any(a in last_message.lower() for a in affirmatives):
            return {"confirmed": True, "correction": None}
        return {"confirmed": False, "correction": last_message}


async def _generate_draft_action(
    domain: str,
    patient_id: str,
    patient_name: str,
    request: str,
) -> dict[str, Any]:
    import datetime as _dt
    review_by = (_dt.datetime.now(tz=_dt.timezone.utc) + _dt.timedelta(days=7)).strftime("%Y-%m-%d")
    prompt = _CREATE_ACTION_PROMPT.format(
        domain=domain,
        patient_id=patient_id,
        patient_name=patient_name,
        request=request,
        review_by=review_by,
    )
    try:
        raw = await asyncio.to_thread(call_claude_json, "You are a care action generator.", prompt, 1000)
        # Ensure required fields
        raw.setdefault("patient_id", patient_id)
        raw.setdefault("domain", domain)
        raw.setdefault("urgency_level", "tier_3")
        raw.setdefault("review_by", review_by)
        return raw
    except Exception as exc:
        return {
            "patient_id": patient_id,
            "domain": domain,
            "type": "care_task",
            "description": request[:200],
            "draft_content": request,
            "urgency_level": "tier_3",
            "review_by": review_by,
            "manual_action_type": None,
            "_generation_error": str(exc),
        }


def _validate_draft(draft: dict) -> list[str]:
    required = ["patient_id", "domain", "type", "description"]
    return [f for f in required if not draft.get(f)]


async def _fetch_question_context(patient_ids: list[str], domain: str | None) -> dict:
    """Build a structured context dict from DB for answering data-centric questions."""
    context: dict = {}

    if patient_ids:
        # Per-patient pending actions and life graph
        context["patients"] = []
        for pid in patient_ids:
            pending = await asyncio.to_thread(get_pending_actions, pid)
            # Slim down to the fields that matter for an LLM summary
            slim_actions = [
                {
                    "action_id": a.get("action_id"),
                    "type": a.get("type"),
                    "domain": a.get("domain"),
                    "description": a.get("description") or a.get("draft_content", "")[:200],
                    "urgency_level": a.get("urgency_level"),
                    "is_overdue": bool(a.get("is_overdue")),
                    "review_by": a.get("review_by"),
                    "manual_action_type": a.get("manual_action_type"),
                }
                for a in pending
            ]
            try:
                life_graph = await asyncio.to_thread(serialize_complete_life_graph, pid) or {}
            except Exception:
                life_graph = {}
            context["patients"].append({
                "patient_id": pid,
                "pending_actions": slim_actions,
                "life_graph": life_graph,
            })
    else:
        # No specific patient — return org-wide ranked actions
        rankings = await asyncio.to_thread(get_action_rankings)
        # Include top 20 to keep prompt size reasonable
        context["all_pending_actions_ranked"] = [
            {
                "action_id": a.get("action_id"),
                "patient_id": a.get("patient_id"),
                "type": a.get("type"),
                "domain": a.get("domain"),
                "description": (a.get("description") or a.get("draft_content", ""))[:200],
                "urgency_level": a.get("urgency_level"),
                "is_overdue": bool(a.get("is_overdue")),
                "score": a.get("score"),
                "review_by": a.get("review_by"),
            }
            for a in rankings[:20]
        ]

    return context


async def _handle_general_chat(
    ctx: Context,
    session_id: str,
    messages: list[dict],
) -> GeneralChatResponse:
    last_msg = _last_user_message(messages)

    # --- Clarification continuation ---
    if _is_in_clarification(messages):
        intent_class, domain, prior_patients = _get_clarification_context(messages)
        confirm = await _check_caregiver_confirmed(last_msg)
        if confirm.get("confirmed"):
            # Proceed to action generation / question answering
            patient_ids = [p["id"] for p in prior_patients]
            pid = patient_ids[0] if patient_ids else None
            if intent_class == "create-action":
                if not pid:
                    reply = "To create an action, I need to know which patient this is for. Could you provide their name?"
                    return GeneralChatResponse(reply=reply, stage="clarifying", intent_class=intent_class, domain=domain, patient_ids=patient_ids)
                patient_record = await asyncio.to_thread(get_patient, pid)
                pname = patient_record.get("name", pid) if patient_record else pid
                # Find the original request (first user message in this flow)
                original_request = messages[0]["content"] if messages else last_msg
                draft = await _generate_draft_action(domain, pid, pname, original_request)
                missing = _validate_draft(draft)
                if missing:
                    reply = f"I wasn't able to generate a complete action draft (missing: {', '.join(missing)}). Could you provide more details?"
                    return GeneralChatResponse(reply=reply, stage="error", intent_class=intent_class, domain=domain, patient_ids=patient_ids)
                draft_id = await asyncio.to_thread(write_staged_action, session_id, draft)
                reply = (
                    f"Here's a draft action for {pname}: **{draft.get('type', 'care task')}** — "
                    f"{draft.get('description', '')}. "
                    f"Would you like to approve it, modify it, or discard it?"
                )
                return GeneralChatResponse(reply=reply, stage="draft_ready", draft_action_id=draft_id, intent_class=intent_class, domain=domain, patient_ids=patient_ids)
            else:
                # Question path — answer directly
                life_graph: dict = {}
                if pid:
                    try:
                        life_graph = await asyncio.to_thread(serialize_complete_life_graph, pid) or {}
                    except Exception:
                        pass
                system_prompt = "You are a care operations assistant. Answer the caregiver's question using the provided patient context. Be concise and clinically accurate."
                user_prompt = f"Question: {last_msg}\n\nPatient context:\n{json.dumps(life_graph, indent=2)}"
                try:
                    answer = await asyncio.to_thread(call_claude, system_prompt, user_prompt, 800)
                except Exception as exc:
                    answer = f"Unable to answer: {exc}"
                return GeneralChatResponse(reply=answer, stage="answered", intent_class=intent_class, domain=domain, patient_ids=patient_ids)
        else:
            # Caregiver corrected — re-classify with full context
            correction = confirm.get("correction") or last_msg
            new_messages = list(messages)
            classification = await _classify_general_chat_intent(new_messages)
            intent_class = classification.get("intent", intent_class)
            domain = classification.get("domain", domain)
            names = await _extract_patient_names(new_messages)
            if not names:
                names = [p.get("name", p["id"]) for p in prior_patients]
            patients = await _resolve_patients_from_names(names)
            if not patients:
                patients = prior_patients
            patient_ids = [p["id"] for p in patients]
            pnames = ", ".join(p["name"] for p in patients) if patients else "the patient"
            verb = "create an action" if intent_class == "create-action" else "answer a question"
            reply = f"Got it. So you'd like to {verb} in the {domain} domain for {pnames} — is that correct?"
            return GeneralChatResponse(reply=reply, stage="clarifying", intent_class=intent_class, domain=domain, patient_ids=patient_ids)

    # --- Fresh classification ---
    classification = await _classify_general_chat_intent(messages)
    intent_class = classification.get("intent", "question")
    domain = classification.get("domain", "health")
    needs_db_query = classification.get("needs_db_query", True)

    if intent_class == "question":
        names = await _extract_patient_names(messages)
        patients = await _resolve_patients_from_names(names)
        patient_ids = [p["id"] for p in patients]

        if needs_db_query:
            # Answer directly from structured DB data — no domain expertise needed
            db_context = await _fetch_question_context(patient_ids, domain)
            system_prompt = (
                "You are a care operations assistant for MACOS. "
                "Answer the caregiver's question using ONLY the structured data provided. "
                "Be specific: cite action descriptions, urgency levels, and overdue status. "
                "If the data shows no relevant records, say so clearly."
            )
            user_prompt = f"Question: {last_msg}\n\nData:\n{json.dumps(db_context, indent=2)}"
        else:
            # Domain expertise needed — use life graph
            life_graph: dict = {}
            if patient_ids:
                try:
                    life_graph = await asyncio.to_thread(serialize_complete_life_graph, patient_ids[0]) or {}
                except Exception:
                    pass
            system_prompt = "You are a care operations assistant. Answer the caregiver's question using the provided patient context. Be concise and clinically accurate."
            user_prompt = f"Question: {last_msg}\n\nPatient context:\n{json.dumps(life_graph, indent=2)}"

        try:
            answer = await asyncio.to_thread(call_claude, system_prompt, user_prompt, 800)
        except Exception as exc:
            answer = f"Unable to answer: {exc}"
        return GeneralChatResponse(reply=answer, stage="answered", intent_class="question", domain=domain, patient_ids=patient_ids)

    # create-action — resolve patients and clarify
    names = await _extract_patient_names(messages)
    patients = await _resolve_patients_from_names(names)
    patient_ids = [p["id"] for p in patients]
    pnames = ", ".join(p["name"] for p in patients) if patients else "the patient"
    domain_label = domain.capitalize()
    reply = f"I'd like to create a {domain_label} action for {pnames}. Is that right? Let me know if you'd like to adjust the domain or patient."
    return GeneralChatResponse(reply=reply, stage="clarifying", intent_class="create-action", domain=domain, patient_ids=patient_ids)


@executor.on_rest_post("/general-chat", GeneralChatRequest, GeneralChatResponse)
async def general_chat(ctx: Context, req: GeneralChatRequest) -> GeneralChatResponse:
    ctx.logger.info("POST /general-chat session_id=%s msgs=%d", req.session_id, len(req.messages))
    return await _handle_general_chat(ctx, req.session_id, [m.dict() for m in req.messages])


@executor.on_rest_post("/general-chat/revise", ReviseRequest, ReviseResponse)
async def general_chat_revise(ctx: Context, req: ReviseRequest) -> ReviseResponse:
    ctx.logger.info("POST /general-chat/revise session_id=%s", req.session_id)
    prompt = _REVISE_ACTION_PROMPT.format(
        original_draft=json.dumps(req.original_draft, indent=2),
        feedback=req.feedback,
    )
    try:
        revised = await asyncio.to_thread(call_claude_json, "", prompt, 512)
    except Exception as exc:
        ctx.logger.error("Revise LLM call failed: %s", exc)
        return ReviseResponse(revised_draft=None, reply=f"Unable to revise: {exc}")

    if not isinstance(revised, dict):
        return ReviseResponse(revised_draft=None, reply="Revision produced an unexpected response. Please try again.")

    reply_parts = []
    if "description" in revised:
        reply_parts.append(f"Updated description: {revised['description']}")
    if "type" in revised:
        reply_parts.append(f"Type: {revised['type']}")
    reply = ". ".join(reply_parts) if reply_parts else "Draft revised based on your feedback."
    return ReviseResponse(revised_draft=revised, reply=reply)


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


@executor.on_rest_post(
    "/internal/expiration-check",
    InternalExpirationCheckRequest,
    InternalExpirationCheckResponse,
)
async def internal_expiration_check(
    ctx: Context, req: InternalExpirationCheckRequest
) -> InternalExpirationCheckResponse:
    """Internal trigger: optionally force one action overdue and run expiration pass immediately."""
    if not _executor_ready:
        ctx.logger.error(
            "POST /internal/expiration-check received but executor event loop is not ready"
        )
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Executor event loop not ready; retry after agent startup completes",
        )

    forced_action_id: str | None = None
    if req.force_overdue:
        target_action_id = req.action_id
        if not target_action_id:
            for candidate in get_action_rankings():
                if not candidate.get("completed") and not candidate.get("is_overdue"):
                    target_action_id = candidate.get("action_id")
                    break

        if target_action_id:
            action = get_action(target_action_id)
            if action:
                now_minus_one = (
                    datetime.now(tz=timezone.utc) - timedelta(minutes=1)
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
                update_action(
                    target_action_id,
                    {
                        "review_by": now_minus_one,
                        "completed": 0,
                        "is_overdue": 0,
                    },
                )
                forced_action_id = target_action_id
                ctx.logger.info(
                    "Forced action to overdue-ready state action_id=%s review_by=%s",
                    target_action_id,
                    now_minus_one,
                )
            else:
                ctx.logger.warning(
                    "Requested force_overdue action_id=%s not found",
                    target_action_id,
                )

    stats = await _run_expiration_pass(ctx)
    return InternalExpirationCheckResponse(
        status="triggered",
        forced_action_id=forced_action_id,
        overdue_found=stats["overdue_found"],
        alerts_sent_dashboard=stats["alerts_sent_dashboard"],
        alerts_sent_asi_one=stats["alerts_sent_asi_one"],
    )


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

    all_pending = request_state.all_requests()
    pending_count = len(all_pending)
    now = datetime.now(tz=timezone.utc)
    oldest_pending_age_seconds = (
        max((now - r.created_at).total_seconds() for r in all_pending.values())
        if all_pending else 0.0
    )
    chat_ingress_age_seconds = (
        (now - _last_chat_ingress_at).total_seconds()
        if _last_chat_ingress_at
        else (now - _started_at).total_seconds()
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

async def _run_expiration_pass(ctx: Context) -> dict[str, int]:
    """Single pass: mark overdue actions and emit deduped notifications."""
    overdue = get_overdue_actions()
    if not overdue:
        return {
            "overdue_found": 0,
            "alerts_sent_dashboard": 0,
            "alerts_sent_asi_one": 0,
        }

    alerts_sent_dashboard = 0
    alerts_sent_asi_one = 0
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
                alerts_sent_dashboard += 1
            elif channel == "asi_one":
                if ASI_ONE_AGENT_ADDRESS:
                    try:
                        await ctx.send(
                            ASI_ONE_AGENT_ADDRESS,
                            ChatMessage(
                                timestamp=datetime.now(tz=timezone.utc),
                                msg_id=uuid4(),
                                content=[
                                    TextContent(
                                        type="text",
                                        text=(
                                            f"⚠️ Overdue action alert\n"
                                            f"Patient: {patient_id}\n"
                                            f"Type: {action.get('type', 'task')}\n"
                                            f"Details: {action.get('description', 'Action review deadline has passed')}\n"
                                            f"Action ID: {action_id}"
                                        ),
                                    ),
                                ],
                            ),
                        )
                        ctx.logger.info(
                            "Sent ASI:One overdue alert action_id=%s target=%s",
                            action_id, ASI_ONE_AGENT_ADDRESS,
                        )
                        alerts_sent_asi_one += 1
                    except Exception as send_err:
                        ctx.logger.error(
                            "Failed to send ASI:One alert action_id=%s: %s", action_id, send_err
                        )
                else:
                    ctx.logger.debug(
                        "ASI_ONE_AGENT_ADDRESS not set, skipping asi_one alert action_id=%s", action_id
                    )
            log_expiration_notification(action_id, channel)
            ctx.logger.info(
                "Expiration notification logged action_id=%s channel=%s", action_id, channel
            )

    return {
        "overdue_found": len(overdue),
        "alerts_sent_dashboard": alerts_sent_dashboard,
        "alerts_sent_asi_one": alerts_sent_asi_one,
    }


@executor.on_interval(period=900.0)
async def expiration_check(ctx: Context) -> None:
    """Mark overdue actions and emit deduped notifications for dashboard + asi_one channels."""
    await _run_expiration_pass(ctx)


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
