"""Health worker — Sprint 2 production implementation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from uagents import Agent, Context

from agents.shared.api_capabilities import worker_api_capability_block
from agents.shared.config import HEALTH_WORKER_SEED, LocalFirstResolver
from agents.shared.constants import AGENT_PORTS, MODIFICATION_MAX_TOKENS, QA_MAX_TOKENS
from agents.shared.llm import build_system_prompt, call_claude, call_claude_json
from agents.shared.models import (
    ActionDraft,
    MockDomainTask,
    MockWorkerResult,
    ModificationDraft,
    ModificationTask,
    OnDemandDetectionRequest,
    QuestionApiResult,
    QuestionTask,
    WorkerResult,
)

worker = Agent(
    name="health-worker",
    seed=HEALTH_WORKER_SEED,
    port=AGENT_PORTS["health_worker"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),
)

_DOMAIN = "health"
_MOCK_API_BASE = os.getenv("MOCK_API_BASE", "http://localhost:8000").rstrip("/")
_MOCK_TIMEOUT_SECONDS = 8.0

_DETECTION_SYSTEM_BASE = (
    "You are a health-domain care assistant. "
    "Your role is to identify actionable health care items for a patient based on their profile. "
    "Focus on: medication checks, OpenFDA drug interactions, prescription refills, "
    "health monitoring requirements, and safety risks. "
    "Return ONLY a valid JSON array of action objects — no markdown, no prose."
)

_DETECTION_USER_TEMPLATE = (
    "Patient ID: {patient_id}\n"
    "Trigger: {trigger}\n"
    "Org context: {org_context}\n\n"
    "{api_guidance}\n\n"
    "Mock API lookup snapshot (if available):\n{cvs_available}\n\n"
    "Domain-scoped patient context JSON:\n{domain_context}\n\n"
    "Correction request metadata (if present):\n{correction_meta}\n\n"
    "Identify up to 3 high-priority health care actions needed for this patient. "
    "Return a JSON array where each element has these exact keys:\n"
    '  type        (string, e.g. "medication_check", "refill", "monitoring")\n'
    "  description (string, concise human-readable description)\n"
    "  draft_content (detailed execution-ready caregiver draft)\n"
    '  urgency_level (one of: "tier_1", "tier_2", "tier_3")\n'
    '  manual_action_type (null or route intent type like "cvs_refill")\n'
    "  api_payload (null or TEMPLATE-V1 object for API-executable tasks)\n"
    "    api_payload must be:\n"
    "    {{\n"
    '      "template_version": "v1",\n'
    '      "call": {{\n'
    '        "route_key": "POST /...",\n'
    '        "provider": "mock" | "live",\n'
    '        "parameters": {{\n'
    '          "field_name": {{"value": <filled value>}}\n'
    "        }}\n"
    "      }}\n"
    "    }}\n"
    "  recipient_email (null or email for notification/execution)\n"
    "  recipient_type (null or one of: caregiver, patient, pharmacy, clinic, prescriber, provider)\n\n"
    "  email_subject (null by default; REQUIRED when recipient_email + recipient_type are set)\n\n"
    "Only use recipient_email values that are present in patient context "
    "(doctor_email, pharmacy_email, or assigned caregiver emails).\n"
    "If no known recipient exists, keep recipient_email/recipient_type/email_subject null.\n\n"
    "Example format:\n"
    '[{{"type": "refill", "description": "...", "draft_content": "...", '
    '"urgency_level": "tier_2", "manual_action_type": "cvs_refill", '
    '"api_payload": {{"template_version": "v1", "call": {{"route_key": "POST /mock/cvs/refill", "provider": "mock", '
    '"parameters": {{"medication": {{"value": "Lisinopril 10mg"}}, "patient_id": {{"value": "pt_001"}}, "pharmacy": {{"value": "CVS Mission St"}} }} }} }}, '
    '"recipient_email": "pharmacy@cvs-mission.example", "recipient_type": "pharmacy", "email_subject": "Refill request: Lisinopril for Margaret Chen"}}]\n\n'
    "Return only the JSON array."
)


def _short(addr: str) -> str:
    return addr[-16:] if len(addr) > 16 else addr


def _trunc(text: str, n: int = 120) -> str:
    return text[:n] + "…" if len(text) > n else text


def _doctor_name_from_context(domain_context: dict) -> str | None:
    patient = domain_context.get("patient") if isinstance(domain_context, dict) else None
    if not isinstance(patient, dict):
        return None
    doctor_name = str(patient.get("doctor_name") or "").strip()
    return doctor_name or None


async def _fetch_cvs_available(ctx: Context, doctor_name: str) -> dict | None:
    url = f"{_MOCK_API_BASE}/mock/cvs/available"
    try:
        async with httpx.AsyncClient(timeout=_MOCK_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params={"doctor_name": doctor_name})
            resp.raise_for_status()
            data = resp.json()
            ctx.logger.info(
                "[MOCK-CALL] domain=%s method=GET path=/mock/cvs/available doctor_name=%r status=%s response=%s",
                _DOMAIN,
                doctor_name,
                resp.status_code,
                _trunc(json.dumps(data), 200),
            )
            return data if isinstance(data, dict) else None
    except Exception as exc:
        response_text = getattr(getattr(exc, "response", None), "text", None)
        ctx.logger.warning(
            "[MOCK-CALL] domain=%s method=GET path=/mock/cvs/available failed: %s response=%s",
            _DOMAIN,
            exc,
            _trunc(response_text or "", 200),
        )
        return None


def _stub_draft(patient_id: str) -> ActionDraft:
    return ActionDraft(
        action_id=f"stub_{uuid4().hex[:8]}",
        patient_id=patient_id,
        domain=_DOMAIN,
        type="detection",
        description="Health detection stub (LLM unavailable)",
        draft_content=None,
        urgency_level="tier_3",
        review_by=(datetime.now(timezone.utc) + timedelta(hours=168)).isoformat(),
        manual_action_type=None,
        api_payload=None,
        recipient_email=None,
        recipient_type=None,
        email_subject=None,
    )


def _parse_detection_response(raw: list | dict, patient_id: str) -> list[ActionDraft]:
    items: list[dict] = raw if isinstance(raw, list) else raw.get("actions", [raw])
    drafts: list[ActionDraft] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        drafts.append(
            ActionDraft(
                action_id=item.get("action_id") or f"act_{uuid4().hex[:12]}",
                patient_id=patient_id,
                domain=_DOMAIN,
                type=item.get("type", "detection"),
                description=item.get("description", "Health action"),
                draft_content=item.get("draft_content"),
                urgency_level=item.get("urgency_level", "tier_3"),
                review_by=item.get(
                    "review_by",
                    (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
                ),
                manual_action_type=item.get("manual_action_type"),
                api_payload=item.get("api_payload"),
                recipient_email=item.get("recipient_email"),
                recipient_type=item.get("recipient_type"),
                email_subject=item.get("email_subject"),
            )
        )
    return drafts or [_stub_draft(patient_id)]


# ---------------------------------------------------------------------------
# Backward-compatible mock handler
# ---------------------------------------------------------------------------


@worker.on_message(MockDomainTask)
async def handle_mock_task(ctx: Context, sender: str, task: MockDomainTask) -> None:
    if task.domain != _DOMAIN:
        return
    ctx.logger.info(
        "[RECV] MockDomainTask request_id=%s query=%r sender=…%s",
        task.request_id,
        _trunc(task.query, 80),
        _short(sender),
    )
    result = MockWorkerResult(
        request_id=task.request_id,
        domain=task.domain,
        worker="health-worker",
        result=f"processed '{task.query}'",
    )
    ctx.logger.info(
        "[SEND] MockWorkerResult request_id=%s -> …%s", task.request_id, _short(sender)
    )
    await ctx.send(sender, result)


# ---------------------------------------------------------------------------
# Production: detection
# ---------------------------------------------------------------------------


@worker.on_message(OnDemandDetectionRequest)
async def handle_detection_request(
    ctx: Context, sender: str, msg: OnDemandDetectionRequest
) -> None:
    if msg.updated_domain != _DOMAIN:
        ctx.logger.warning(
            "[RECV][IGNORE] OnDemandDetectionRequest pass_id=%s updated_domain=%s "
            "expected=%s sender=…%s",
            msg.pass_id,
            msg.updated_domain,
            _DOMAIN,
            _short(sender),
        )
        return

    ctx.logger.info(
        "[RECV] OnDemandDetectionRequest pass_id=%s patient_id=%s trigger=%s "
        "org_context_keys=%s context_keys=%s sender=…%s",
        msg.pass_id,
        msg.patient_id,
        msg.trigger,
        list((msg.org_context or {}).keys()),
        sorted((msg.domain_patient_context or {}).keys()),
        _short(sender),
    )

    domain_context = msg.domain_patient_context or {}
    if not domain_context:
        ctx.logger.error(
            "[VALIDATE] Missing domain_patient_context pass_id=%s patient_id=%s domain=%s",
            msg.pass_id,
            msg.patient_id,
            _DOMAIN,
        )
    context_bytes = len(json.dumps(domain_context, default=str))
    ctx.logger.info(
        "[PARSE] pass_id=%s domain=%s context_keys=%s context_bytes=%s",
        msg.pass_id,
        _DOMAIN,
        sorted(domain_context.keys()),
        context_bytes,
    )

    system_prompt = build_system_prompt(
        _DETECTION_SYSTEM_BASE, msg.org_context or {}, _DOMAIN
    )
    api_guidance = worker_api_capability_block(_DOMAIN)
    doctor_name = _doctor_name_from_context(domain_context)
    if not doctor_name:
        ctx.logger.warning(
            "[MOCK-CALL] domain=%s doctor_name missing in patient context for patient_id=%s; skipping /mock/cvs/available",
            _DOMAIN,
            msg.patient_id,
        )
        cvs_available = None
    else:
        cvs_available = await _fetch_cvs_available(ctx, doctor_name)
    correction_meta = (msg.snapshot_meta or {}).get("detection_correction")
    user_prompt = _DETECTION_USER_TEMPLATE.format(
        patient_id=msg.patient_id,
        trigger=msg.trigger,
        org_context=json.dumps(msg.org_context or {}),
        api_guidance=api_guidance,
        cvs_available=json.dumps(cvs_available or {}, indent=2),
        domain_context=json.dumps(domain_context, indent=2),
        correction_meta=json.dumps(correction_meta or {}, indent=2),
    )

    ctx.logger.info(
        "[LLM-CALL] domain=%s intent=detection patient_id=%s trigger=%s max_tokens=1000 "
        "system_preview=%r",
        _DOMAIN,
        msg.patient_id,
        msg.trigger,
        _trunc(system_prompt, 120),
    )

    drafts: list[ActionDraft] = []
    try:
        raw = call_claude_json(system_prompt, user_prompt, max_tokens=1000)
        raw_type = type(raw).__name__
        raw_len = len(raw) if isinstance(raw, (list, dict)) else 0
        ctx.logger.info(
            "[LLM-RESULT] domain=%s patient_id=%s raw_type=%s raw_len=%d",
            _DOMAIN,
            msg.patient_id,
            raw_type,
            raw_len,
        )
        drafts = _parse_detection_response(raw, msg.patient_id)
        ctx.logger.info(
            "[PARSE] %d drafts parsed for patient_id=%s pass_id=%s",
            len(drafts),
            msg.patient_id,
            msg.pass_id,
        )
        for i, d in enumerate(drafts):
            ctx.logger.info(
                "[DRAFT] %d/%d action_id=%s type=%s urgency=%s desc=%r",
                i + 1,
                len(drafts),
                d.action_id,
                d.type,
                d.urgency_level,
                _trunc(d.description, 80),
            )
    except RuntimeError as exc:
        ctx.logger.warning(
            "[LLM-FAIL] LLM unavailable for detection patient_id=%s pass_id=%s: %s "
            "— returning stub draft",
            msg.patient_id,
            msg.pass_id,
            exc,
        )
        drafts = [_stub_draft(msg.patient_id)]
    except Exception as exc:
        ctx.logger.error(
            "[LLM-FAIL] Unexpected error during detection patient_id=%s pass_id=%s: %s "
            "— returning stub draft",
            msg.patient_id,
            msg.pass_id,
            exc,
        )
        drafts = [_stub_draft(msg.patient_id)]

    result = WorkerResult(
        pass_id=msg.pass_id,
        patient_id=msg.patient_id,
        domain=_DOMAIN,
        drafts=drafts,
    )
    ctx.logger.info(
        "[SEND] WorkerResult pass_id=%s patient_id=%s drafts=%d -> supervisor …%s",
        msg.pass_id,
        msg.patient_id,
        len(drafts),
        _short(sender),
    )
    await ctx.send(sender, result)


# ---------------------------------------------------------------------------
# Production: modification
# ---------------------------------------------------------------------------


@worker.on_message(ModificationTask)
async def handle_modification_task(
    ctx: Context, sender: str, task: ModificationTask
) -> None:
    ctx.logger.info(
        "[RECV] ModificationTask action_id=%s patient_id=%s action_type=%s "
        "current_draft_len=%d instruction=%r sender=…%s",
        task.action_id,
        task.patient_id,
        task.action_type,
        len(task.current_draft),
        _trunc(task.modification_instruction, 100),
        _short(sender),
    )

    system_prompt = (
        "You are a health-domain care assistant. "
        "Revise the provided draft according to the modification instruction. "
        "Return ONLY the revised draft text — no markdown, no preamble."
    )
    user_prompt = (
        f"Action type: {task.action_type}\n"
        f"Current draft:\n{task.current_draft}\n\n"
        f"Modification instruction: {task.modification_instruction}\n\n"
        "Write the revised draft and then, on a new line starting with 'CHANGES:', "
        "provide a one-sentence summary of what changed."
    )

    ctx.logger.info(
        "[LLM-CALL] domain=%s intent=modification action_id=%s max_tokens=%d",
        _DOMAIN,
        task.action_id,
        MODIFICATION_MAX_TOKENS,
    )

    revised_draft = ""
    changes_summary = ""
    try:
        raw_response = call_claude(
            system_prompt, user_prompt, max_tokens=MODIFICATION_MAX_TOKENS
        )
        ctx.logger.info(
            "[LLM-RESULT] action_id=%s response_len=%d has_changes_marker=%s",
            task.action_id,
            len(raw_response),
            "CHANGES:" in raw_response,
        )
        if "CHANGES:" in raw_response:
            parts = raw_response.split("CHANGES:", 1)
            revised_draft = parts[0].strip()
            changes_summary = parts[1].strip()
        else:
            revised_draft = raw_response.strip()
            changes_summary = "Draft revised per instruction."
        ctx.logger.info(
            "[LLM-RESULT] action_id=%s revised_len=%d changes=%r",
            task.action_id,
            len(revised_draft),
            _trunc(changes_summary, 80),
        )
    except RuntimeError as exc:
        ctx.logger.warning(
            "[LLM-FAIL] LLM unavailable for modification action_id=%s: %s "
            "— returning original draft",
            task.action_id,
            exc,
        )
        revised_draft = task.current_draft
        changes_summary = "LLM unavailable — original draft retained."
    except Exception as exc:
        ctx.logger.error(
            "[LLM-FAIL] Unexpected error during modification action_id=%s: %s "
            "— returning original draft",
            task.action_id,
            exc,
        )
        revised_draft = task.current_draft
        changes_summary = "LLM error — original draft retained."

    draft_result = ModificationDraft(
        action_id=task.action_id,
        revised_draft=revised_draft,
        changes_summary=changes_summary,
    )
    ctx.logger.info(
        "[SEND] ModificationDraft action_id=%s revised_len=%d changes=%r -> supervisor …%s",
        task.action_id,
        len(revised_draft),
        _trunc(changes_summary, 80),
        _short(sender),
    )
    await ctx.send(sender, draft_result)


# ---------------------------------------------------------------------------
# Production: question
# ---------------------------------------------------------------------------


@worker.on_message(QuestionTask)
async def handle_question_task(ctx: Context, sender: str, task: QuestionTask) -> None:
    ctx.logger.info(
        "[RECV] QuestionTask action_id=%s patient_id=%s domain=%s question=%r sender=…%s",
        task.action_id,
        task.patient_id,
        task.domain,
        _trunc(task.question, 100),
        _short(sender),
    )

    # api_lookup_instruction carries the JSON-serialised patient life graph fetched
    # by the supervisor from the database. Log whether we have real data or not.
    has_patient_data = bool(
        task.api_lookup_instruction and task.api_lookup_instruction != "{}"
    )
    ctx.logger.info(
        "[CONTEXT] action_id=%s has_patient_data=%s patient_data_len=%d",
        task.action_id,
        has_patient_data,
        len(task.api_lookup_instruction or ""),
    )

    system_prompt = (
        "You are a health-domain care assistant. "
        "You will be given a patient's full record from the database followed by a question. "
        "Answer the question using ONLY the patient data provided. "
        "If the data does not contain the answer, say exactly what information is missing. "
        "Do not speculate or invent data."
    )
    patient_section = (
        task.api_lookup_instruction
        if has_patient_data
        else "No patient record was found in the database for this patient ID."
    )
    user_prompt = (
        f"Patient ID: {task.patient_id}\n\n"
        f"Patient record from database:\n{patient_section}\n\n"
        f"Question: {task.question}\n\n"
        "Answer the question based solely on the patient record above."
    )

    ctx.logger.info(
        "[LLM-CALL] domain=%s intent=question action_id=%s max_tokens=%d question=%r",
        _DOMAIN,
        task.action_id,
        QA_MAX_TOKENS,
        _trunc(task.question, 80),
    )

    answer_text = ""
    try:
        answer_text = call_claude(system_prompt, user_prompt, max_tokens=QA_MAX_TOKENS)
        ctx.logger.info(
            "[LLM-RESULT] action_id=%s answer_len=%d answer_preview=%r",
            task.action_id,
            len(answer_text),
            _trunc(answer_text, 120),
        )
    except RuntimeError as exc:
        ctx.logger.warning(
            "[LLM-FAIL] LLM unavailable for question action_id=%s: %s",
            task.action_id,
            exc,
        )
        answer_text = "LLM unavailable — please consult a caregiver for this question."
    except Exception as exc:
        ctx.logger.error(
            "[LLM-FAIL] Unexpected error during question action_id=%s: %s",
            task.action_id,
            exc,
        )
        answer_text = "Unable to retrieve answer at this time."

    api_result = QuestionApiResult(
        action_id=task.action_id,
        api_data=answer_text,
    )
    ctx.logger.info(
        "[SEND] QuestionApiResult action_id=%s answer_len=%d -> supervisor …%s",
        task.action_id,
        len(answer_text),
        _short(sender),
    )
    await ctx.send(sender, api_result)


if __name__ == "__main__":
    worker.run()
