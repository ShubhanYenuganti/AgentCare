"""Financial worker — Sprint 2 production implementation."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from uagents import Agent, Context

from agents.shared.db import serialize_life_graph

from agents.shared.api_capabilities import worker_api_capability_block
from agents.shared.config import FINANCIAL_WORKER_SEED, LocalFirstResolver
from agents.shared.constants import AGENT_PORTS
from agents.shared.llm import build_system_prompt, call_claude, call_claude_json
from agents.shared.models import (
    ActionDraft,
    ModificationDraft,
    ModificationTask,
    MockDomainTask,
    MockWorkerResult,
    OnDemandDetectionRequest,
    QuestionApiResult,
    QuestionTask,
    WorkerResult,
)

worker = Agent(
    name="financial-worker",
    seed=FINANCIAL_WORKER_SEED,
    port=AGENT_PORTS["financial_worker"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),
)

_DOMAIN = "financial"

_DETECTION_BASE_PROMPT = """You are a financial care specialist for a home-care organisation.

Analyse the patient context and generate a JSON list of action objects. Focus on:
- Bill payment deadlines: identify upcoming bills, due dates, and risk of late fees
- Auto-pay setup: flag bills that could benefit from automated payment
- Insurance claims: identify pending claims, denials, or appeals needed
- Medicare/Medicaid benefits check: verify the patient is receiving all entitled benefits
- Financial assistance programs: identify grants, subsidies, or aid programmes the patient may qualify for

Return a JSON array. Each element must be an object with exactly these keys:
{
  "description": "<short human-readable label>",
  "type": "detection",
  "draft_content": "<detailed draft text for the caregiver>",
  "urgency_level": "tier_1" | "tier_2" | "tier_3",
  "manual_action_type": null | "<type string>",
  "api_payload": null | {
    "template_version": "v1",
    "call": {
      "route_key": "POST /...",
      "provider": "mock" | "live",
      "parameters": {
        "<field_name>": {"value": <filled_value>}
      }
    }
  },
  "recipient_email": null | "<email>",
  "recipient_type": null | "caregiver" | "patient" | "pharmacy" | "clinic" | "prescriber" | "provider",
  "email_subject": null | "<subject required when recipient_email+recipient_type are set>"
}

For API-executable actions, always emit template_version v1 payload and fill each
parameters.<field>.value node. Do not emit raw request-body JSON.
Only use recipient_email values present in patient context
(doctor_email, pharmacy_email, or assigned caregiver emails).
If no known recipient exists, keep recipient_email/recipient_type/email_subject null.

Return only the JSON array — no prose, no markdown fences."""

_MODIFICATION_BASE_PROMPT = (
    "You are a financial care specialist revising an action draft. "
    "Apply the modification instruction precisely. Keep the tone professional and concise. "
    "Return only the revised draft text — no commentary."
)

_QUESTION_BASE_PROMPT = (
    "You are a financial care specialist answering a caregiver question. "
    "Use the provided action context to give a clear, evidence-based answer. "
    "Return only the answer text — no commentary."
)


def _run_financial_rule_checks(life_graph: dict, patient_id: str) -> list[dict]:
    items: list[dict] = []
    today = datetime.now(timezone.utc).date()

    # Rule 1: Bill due alert (5-day window)
    for bill in life_graph.get("financial_bills", []):
        if not bill.get("active", 1):
            continue
        due_str = bill.get("due_date")
        if not due_str:
            continue
        try:
            due_date = date.fromisoformat(due_str)
        except ValueError:
            continue
        days_until = (due_date - today).days
        if 0 <= days_until <= 5:
            urgency = "tier_1" if days_until <= 2 else "tier_2"
            items.append({
                "type": "bill_due_alert",
                "urgency": urgency,
                "description": (
                    f"Bill '{bill.get('name')}' of ${bill.get('amount', 'N/A')} "
                    f"due in {days_until} day(s) on {due_str}"
                ),
                "draft_content": (
                    f"Patient {patient_id} has a bill '{bill.get('name')}' "
                    f"for ${bill.get('amount', 'N/A')} due on {due_str} "
                    f"({days_until} day(s) remaining). Please ensure payment is arranged."
                ),
            })

    # Rule 2: Missed autopay (autopay=1, past due)
    for bill in life_graph.get("financial_bills", []):
        if not bill.get("active", 1):
            continue
        if not bill.get("autopay"):
            continue
        due_str = bill.get("due_date")
        if not due_str:
            continue
        try:
            due_date = date.fromisoformat(due_str)
        except ValueError:
            continue
        if due_date < today:
            items.append({
                "type": "missed_autopay",
                "urgency": "tier_1",
                "description": (
                    f"Autopay missed for bill '{bill.get('name')}' of ${bill.get('amount', 'N/A')} "
                    f"(was due {due_str})"
                ),
                "draft_content": (
                    f"Patient {patient_id}'s autopay failed for '{bill.get('name')}' "
                    f"(${bill.get('amount', 'N/A')}) which was due on {due_str}. "
                    "Please investigate the autopay failure and arrange manual payment."
                ),
            })

    # Rule 3: Spending anomaly
    anomalies = life_graph.get("financial_anomalies", [])
    current_month = today.strftime("%Y-%m")
    current_month_count = sum(
        1 for a in anomalies
        if (a.get("detected_at") or "").startswith(current_month)
    )
    trailing_count = len(anomalies) - current_month_count
    trailing_avg = trailing_count / 3.0 if trailing_count > 0 else 0
    flagged = False
    if trailing_avg > 0 and current_month_count > (trailing_avg * 1.5):
        flagged = True
    elif current_month_count >= 3:
        flagged = True
    if flagged:
        items.append({
            "type": "spending_anomaly",
            "urgency": "tier_2",
            "description": (
                f"Elevated spending anomalies this month: {current_month_count} detected "
                f"(trailing avg: {trailing_avg:.1f}/month)"
            ),
            "draft_content": (
                f"Patient {patient_id} has {current_month_count} financial anomalies detected "
                f"in {current_month}, compared to a trailing average of {trailing_avg:.1f}/month. "
                "Please review recent transactions for irregularities."
            ),
        })

    return items


def _short(addr: str) -> str:
    return addr[-16:] if len(addr) > 16 else addr


def _trunc(text: str, n: int = 120) -> str:
    return text[:n] + "…" if len(text) > n else text


def _stub_draft(patient_id: str) -> ActionDraft:
    return ActionDraft(
        action_id=f"stub_{uuid4().hex[:8]}",
        patient_id=patient_id,
        domain=_DOMAIN,
        type="detection",
        description="Financial detection stub (LLM unavailable)",
        draft_content=None,
        urgency_level="tier_3",
        review_by=(datetime.now(timezone.utc) + timedelta(hours=168)).isoformat(),
        manual_action_type=None,
        api_payload=None,
        recipient_email=None,
        recipient_type=None,
        email_subject=None,
    )


def _parse_drafts(raw: list[dict], patient_id: str, pass_id: str) -> list[ActionDraft]:
    drafts: list[ActionDraft] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        drafts.append(
            ActionDraft(
                action_id=f"fin_{pass_id[:8]}_{uuid4().hex[:6]}",
                patient_id=patient_id,
                domain=_DOMAIN,
                type=item.get("type", "detection"),
                description=item.get("description", "Financial action"),
                draft_content=item.get("draft_content"),
                urgency_level=item.get("urgency_level", "tier_3"),
                review_by=(datetime.now(timezone.utc) + timedelta(hours=168)).isoformat(),
                manual_action_type=item.get("manual_action_type"),
                api_payload=item.get("api_payload"),
                recipient_email=item.get("recipient_email"),
                recipient_type=item.get("recipient_type"),
                email_subject=item.get("email_subject"),
            )
        )
    return drafts


# ---------------------------------------------------------------------------
# Backward-compat mock handler
# ---------------------------------------------------------------------------

@worker.on_message(MockDomainTask)
async def handle_mock_task(ctx: Context, sender: str, task: MockDomainTask) -> None:
    if task.domain != _DOMAIN:
        return
    ctx.logger.info(
        "[RECV] MockDomainTask request_id=%s query=%r sender=…%s",
        task.request_id, _trunc(task.query, 80), _short(sender),
    )
    result = MockWorkerResult(
        request_id=task.request_id,
        domain=task.domain,
        worker="financial-worker",
        result=f"processed '{task.query}'",
    )
    ctx.logger.info(
        "[SEND] MockWorkerResult request_id=%s -> …%s", task.request_id, _short(sender),
    )
    await ctx.send(sender, result)


# ---------------------------------------------------------------------------
# Production: detection
# ---------------------------------------------------------------------------

@worker.on_message(OnDemandDetectionRequest)
async def handle_detection(
    ctx: Context, sender: str, msg: OnDemandDetectionRequest
) -> None:
    ctx.logger.info(
        "[RECV] OnDemandDetectionRequest pass_id=%s patient_id=%s trigger=%s "
        "org_context_keys=%s context_keys=%s sender=…%s",
        msg.pass_id, msg.patient_id, msg.trigger,
        list((msg.org_context or {}).keys()),
        sorted((msg.domain_patient_context or {}).keys()),
        _short(sender),
    )

    domain_context = msg.domain_patient_context or {}
    if not domain_context:
        ctx.logger.error(
            "[VALIDATE] Missing domain_patient_context pass_id=%s patient_id=%s domain=%s",
            msg.pass_id, msg.patient_id, _DOMAIN,
        )
    context_bytes = len(json.dumps(domain_context, default=str))
    ctx.logger.info(
        "[PARSE] pass_id=%s domain=%s context_keys=%s context_bytes=%s",
        msg.pass_id, _DOMAIN, sorted(domain_context.keys()), context_bytes,
    )

    system = build_system_prompt(_DETECTION_BASE_PROMPT, msg.org_context or {}, _DOMAIN)
    api_guidance = worker_api_capability_block(_DOMAIN)
    correction_meta = (msg.snapshot_meta or {}).get("detection_correction")
    user_prompt = (
        f"Patient ID: {msg.patient_id}\n"
        f"Trigger: {msg.trigger}\n"
        f"Org context: {json.dumps(msg.org_context or {})}\n\n"
        f"{api_guidance}\n\n"
        f"Domain-scoped patient context JSON:\n{json.dumps(domain_context, indent=2)}\n\n"
        f"Correction request metadata (if present):\n{json.dumps(correction_meta or {}, indent=2)}\n\n"
        "Generate financial care action drafts for this patient."
    )

    ctx.logger.info(
        "[LLM-CALL] domain=%s intent=detection patient_id=%s trigger=%s max_tokens=2000 "
        "system_preview=%r",
        _DOMAIN, msg.patient_id, msg.trigger, _trunc(system, 120),
    )

    rule_drafts: list[ActionDraft] = []
    try:
        life_graph = await asyncio.to_thread(serialize_life_graph, msg.patient_id)
        if life_graph:
            rule_items = await asyncio.to_thread(_run_financial_rule_checks, life_graph, msg.patient_id)
            rule_drafts = [
                ActionDraft(
                    action_id=f"rule_{uuid4().hex[:12]}",
                    patient_id=msg.patient_id,
                    domain=_DOMAIN,
                    type=item["type"],
                    description=item["description"],
                    draft_content=item.get("draft_content"),
                    urgency_level=item["urgency"],
                    review_by=(datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
                    manual_action_type=None,
                    api_payload=None,
                    recipient_email=None,
                    recipient_type=None,
                    email_subject=None,
                )
                for item in rule_items
            ]
            ctx.logger.info("[RULE-CHECK] pass_id=%s rule_drafts=%d", msg.pass_id, len(rule_drafts))
    except Exception as exc:
        ctx.logger.error("[RULE-CHECK] Failed pass_id=%s: %s", msg.pass_id, exc)

    drafts: list[ActionDraft] = []
    try:
        raw = call_claude_json(system, user_prompt, max_tokens=2000)
        raw_type = type(raw).__name__
        raw_len = len(raw) if isinstance(raw, (list, dict)) else 0
        ctx.logger.info(
            "[LLM-RESULT] domain=%s patient_id=%s raw_type=%s raw_len=%d",
            _DOMAIN, msg.patient_id, raw_type, raw_len,
        )
        if isinstance(raw, list):
            drafts = _parse_drafts(raw, msg.patient_id, msg.pass_id)
        else:
            ctx.logger.warning(
                "[LLM-RESULT][UNEXPECTED] Expected list, got %s for pass_id=%s — using stub",
                raw_type, msg.pass_id,
            )
            drafts = [_stub_draft(msg.patient_id)]

        ctx.logger.info(
            "[PARSE] %d drafts parsed for patient_id=%s pass_id=%s",
            len(drafts), msg.patient_id, msg.pass_id,
        )
        for i, d in enumerate(drafts):
            ctx.logger.info(
                "[DRAFT] %d/%d action_id=%s type=%s urgency=%s desc=%r",
                i + 1, len(drafts), d.action_id, d.type, d.urgency_level,
                _trunc(d.description, 80),
            )
        # Merge: rule drafts first, then LLM drafts for new types
        seen_types = {d.type for d in rule_drafts}
        merged = list(rule_drafts)
        for d in drafts:
            if d.type not in seen_types:
                merged.append(d)
                seen_types.add(d.type)
        drafts = merged if merged else [_stub_draft(msg.patient_id)]
    except RuntimeError as exc:
        ctx.logger.warning(
            "[LLM-FAIL] LLM unavailable for detection patient_id=%s pass_id=%s: %s "
            "— returning stub draft",
            msg.patient_id, msg.pass_id, exc,
        )
        drafts = rule_drafts if rule_drafts else [_stub_draft(msg.patient_id)]
    except Exception as exc:
        ctx.logger.error(
            "[LLM-FAIL] Unexpected error during detection patient_id=%s pass_id=%s: %s "
            "— returning stub draft",
            msg.patient_id, msg.pass_id, exc,
        )
        drafts = rule_drafts if rule_drafts else [_stub_draft(msg.patient_id)]

    if not drafts:
        drafts = [_stub_draft(msg.patient_id)]

    result = WorkerResult(
        pass_id=msg.pass_id,
        patient_id=msg.patient_id,
        domain=_DOMAIN,
        drafts=drafts,
    )
    ctx.logger.info(
        "[SEND] WorkerResult pass_id=%s patient_id=%s drafts=%d -> supervisor …%s",
        msg.pass_id, msg.patient_id, len(drafts), _short(sender),
    )
    await ctx.send(sender, result)


# ---------------------------------------------------------------------------
# Production: modification
# ---------------------------------------------------------------------------

@worker.on_message(ModificationTask)
async def handle_modification(
    ctx: Context, sender: str, task: ModificationTask
) -> None:
    ctx.logger.info(
        "[RECV] ModificationTask action_id=%s patient_id=%s action_type=%s "
        "current_draft_len=%d instruction=%r sender=…%s",
        task.action_id, task.patient_id, task.action_type,
        len(task.current_draft), _trunc(task.modification_instruction, 100), _short(sender),
    )

    user_prompt = (
        f"Action type: {task.action_type}\n"
        f"Current draft:\n{task.current_draft}\n\n"
        f"Modification instruction: {task.modification_instruction}"
    )

    ctx.logger.info(
        "[LLM-CALL] domain=%s intent=modification action_id=%s max_tokens=1500",
        _DOMAIN, task.action_id,
    )

    revised = task.current_draft
    changes_summary = "LLM unavailable — draft unchanged"
    try:
        revised = call_claude(_MODIFICATION_BASE_PROMPT, user_prompt, max_tokens=1500)
        changes_summary = f"Applied: {task.modification_instruction}"
        ctx.logger.info(
            "[LLM-RESULT] action_id=%s revised_len=%d changes=%r",
            task.action_id, len(revised), _trunc(changes_summary, 80),
        )
    except RuntimeError as exc:
        ctx.logger.warning(
            "[LLM-FAIL] LLM unavailable for modification action_id=%s: %s "
            "— returning original draft",
            task.action_id, exc,
        )
    except Exception as exc:
        ctx.logger.error(
            "[LLM-FAIL] Unexpected error during modification action_id=%s: %s "
            "— returning original draft",
            task.action_id, exc,
        )
        changes_summary = f"Error during modification: {exc}"

    draft = ModificationDraft(
        action_id=task.action_id,
        revised_draft=revised,
        changes_summary=changes_summary,
    )
    ctx.logger.info(
        "[SEND] ModificationDraft action_id=%s revised_len=%d changes=%r -> supervisor …%s",
        task.action_id, len(revised), _trunc(changes_summary, 80), _short(sender),
    )
    await ctx.send(sender, draft)


# ---------------------------------------------------------------------------
# Production: question
# ---------------------------------------------------------------------------

@worker.on_message(QuestionTask)
async def handle_question(
    ctx: Context, sender: str, task: QuestionTask
) -> None:
    ctx.logger.info(
        "[RECV] QuestionTask action_id=%s patient_id=%s domain=%s question=%r sender=…%s",
        task.action_id, task.patient_id, task.domain,
        _trunc(task.question, 100), _short(sender),
    )

    has_patient_data = bool(task.api_lookup_instruction and task.api_lookup_instruction != "{}")
    ctx.logger.info(
        "[CONTEXT] action_id=%s has_patient_data=%s patient_data_len=%d",
        task.action_id, has_patient_data, len(task.api_lookup_instruction or ""),
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
        "[LLM-CALL] domain=%s intent=question action_id=%s max_tokens=1000 question=%r",
        _DOMAIN, task.action_id, _trunc(task.question, 80),
    )

    answer_text = f"LLM unavailable. Question: {task.question}"
    try:
        answer_text = call_claude(_QUESTION_BASE_PROMPT, user_prompt, max_tokens=1000)
        ctx.logger.info(
            "[LLM-RESULT] action_id=%s answer_len=%d answer_preview=%r",
            task.action_id, len(answer_text), _trunc(answer_text, 120),
        )
    except RuntimeError as exc:
        ctx.logger.warning(
            "[LLM-FAIL] LLM unavailable for question action_id=%s: %s",
            task.action_id, exc,
        )
    except Exception as exc:
        ctx.logger.error(
            "[LLM-FAIL] Unexpected error during question action_id=%s: %s",
            task.action_id, exc,
        )
        answer_text = f"Error answering question: {exc}"

    api_result = QuestionApiResult(
        action_id=task.action_id,
        api_data=answer_text,
    )
    ctx.logger.info(
        "[SEND] QuestionApiResult action_id=%s answer_len=%d -> supervisor …%s",
        task.action_id, len(answer_text), _short(sender),
    )
    await ctx.send(sender, api_result)


if __name__ == "__main__":
    worker.run()
