"""Financial supervisor — Sprint 2 production implementation."""

from __future__ import annotations

import os
from pathlib import Path

from uagents import Agent, Context

_MOCK_FALLBACK = os.getenv("SPRINT2_MOCK_FALLBACK", "").lower() in ("1", "true", "yes")

from agents.shared.config import (
    FINANCIAL_SUPERVISOR_SEED,
    FINANCIAL_WORKER_ADDRESS,
    LocalFirstResolver,
)
from agents.shared.api_capabilities import validate_detection_draft_for_api_requirements
from agents.shared.constants import AGENT_PORTS
import json

from agents.shared.db import replace_draft, serialize_life_graph, set_modification_in_progress, write_action
from agents.shared.life_graph_parser import parse_life_graph_for_domain
from agents.shared.models import (
    MockDomainTask,
    MockSupervisorResult,
    MockWorkerResult,
    ModificationDraft,
    ModificationRequest,
    ModificationResult,
    ModificationTask,
    OnDemandDetectionRequest,
    QuestionAnswer,
    QuestionApiResult,
    QuestionRequest,
    QuestionTask,
    SupervisorResult,
    WorkerResult,
)

supervisor = Agent(
    name="financial-supervisor",
    seed=FINANCIAL_SUPERVISOR_SEED,
    port=AGENT_PORTS["financial_supervisor"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),
)

_pending_executor_by_request_id: dict[str, str] = {}
_pending_executor_detection: dict[str, str] = {}
_pending_executor_modification: dict[str, str] = {}
_pending_executor_question: dict[str, str] = {}
_pending_detection_worker_request: dict[str, OnDemandDetectionRequest] = {}
_pending_detection_retry_count: dict[str, int] = {}
_MAX_DETECTION_RETRY = 1

_DOMAIN = "financial"


def _short(addr: str) -> str:
    return addr[-16:] if len(addr) > 16 else addr


def _trunc(text: str, n: int = 120) -> str:
    return text[:n] + "…" if len(text) > n else text


def _state_summary() -> str:
    return (
        f"pending_detection={len(_pending_executor_detection)} "
        f"pending_mod={len(_pending_executor_modification)} "
        f"pending_q={len(_pending_executor_question)}"
    )


def _known_recipient_emails_from_detection_request(
    msg: OnDemandDetectionRequest | None,
) -> set[str]:
    context = msg.domain_patient_context if msg else {}
    if not isinstance(context, dict):
        return set()

    emails: set[str] = set()
    patient = context.get("patient")
    if isinstance(patient, dict):
        for key in ("doctor_email", "pharmacy_email"):
            value = str(patient.get(key) or "").strip().lower()
            if value:
                emails.add(value)

    caregivers = context.get("caregivers")
    if isinstance(caregivers, list):
        for item in caregivers:
            if not isinstance(item, dict):
                continue
            value = str(item.get("email") or "").strip().lower()
            if value:
                emails.add(value)
    return emails


def _validate_detection_drafts_for_api_fields(
    result: WorkerResult,
    known_recipient_emails: set[str],
) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    for draft in result.drafts:
        draft_errors = validate_detection_draft_for_api_requirements(
            draft.dict(),
            known_recipient_emails=known_recipient_emails,
        )
        if draft_errors:
            errors.append(
                {
                    "action_id": draft.action_id,
                    "manual_action_type": draft.manual_action_type,
                    "errors": draft_errors,
                }
            )
    return errors


# ---------------------------------------------------------------------------
# Backward-compat mock handlers
# ---------------------------------------------------------------------------

@supervisor.on_message(MockDomainTask)
async def handle_mock_task(ctx: Context, sender: str, task: MockDomainTask) -> None:
    if task.domain != _DOMAIN:
        ctx.logger.warning(
            "[RECV][IGNORE] MockDomainTask request_id=%s domain=%s expected=%s sender=…%s",
            task.request_id, task.domain, _DOMAIN, _short(sender),
        )
        return
    if not _MOCK_FALLBACK:
        ctx.logger.warning(
            "[DEPRECATED] MockDomainTask on financial supervisor. "
            "Set SPRINT2_MOCK_FALLBACK=true to re-enable. request_id=%s",
            task.request_id,
        )
        return
    ctx.logger.info(
        "[RECV] MockDomainTask request_id=%s domain=%s query=%r sender=…%s",
        task.request_id, task.domain, _trunc(task.query, 80), _short(sender),
    )
    _pending_executor_by_request_id[task.request_id] = sender
    forwarded = task.copy(
        update={"metadata": {**(task.metadata or {}), "financial_supervisor": "forwarded"}}
    )
    ctx.logger.info(
        "[ROUTE] MockDomainTask request_id=%s -> financial-worker …%s",
        task.request_id, _short(FINANCIAL_WORKER_ADDRESS),
    )
    await ctx.send(FINANCIAL_WORKER_ADDRESS, forwarded)


@supervisor.on_message(MockWorkerResult)
async def handle_mock_worker_result(
    ctx: Context, worker_sender: str, result: MockWorkerResult
) -> None:
    if result.domain != _DOMAIN:
        ctx.logger.warning(
            "[RECV][IGNORE] MockWorkerResult request_id=%s domain=%s expected=%s sender=…%s",
            result.request_id, result.domain, _DOMAIN, _short(worker_sender),
        )
        return
    ctx.logger.info(
        "[RECV] MockWorkerResult request_id=%s worker=%s result=%r sender=…%s",
        result.request_id, result.worker, _trunc(result.result, 80), _short(worker_sender),
    )
    executor_address = _pending_executor_by_request_id.pop(result.request_id, None)
    if executor_address is None:
        ctx.logger.warning(
            "[STATE][MISS] No pending executor for mock request_id=%s — dropping",
            result.request_id,
        )
        return
    response = MockSupervisorResult(
        request_id=result.request_id,
        domain=result.domain,
        supervisor="financial-supervisor",
        result=f"Financial mock complete via {result.worker}: {result.result}",
    )
    ctx.logger.info(
        "[SEND] MockSupervisorResult request_id=%s -> executor …%s",
        result.request_id, _short(executor_address),
    )
    await ctx.send(executor_address, response)


# ---------------------------------------------------------------------------
# Production: detection
# ---------------------------------------------------------------------------

@supervisor.on_message(OnDemandDetectionRequest)
async def handle_detection_request(
    ctx: Context, sender: str, msg: OnDemandDetectionRequest
) -> None:
    if msg.updated_domain and msg.updated_domain != _DOMAIN:
        ctx.logger.warning(
            "[RECV][IGNORE] OnDemandDetectionRequest pass_id=%s updated_domain=%s "
            "expected=%s sender=…%s",
            msg.pass_id, msg.updated_domain, _DOMAIN, _short(sender),
        )
        return

    ctx.logger.info(
        "[RECV] OnDemandDetectionRequest pass_id=%s patient_id=%s trigger=%s "
        "org_context_keys=%s snapshot_keys=%s sender=…%s | %s",
        msg.pass_id, msg.patient_id, msg.trigger,
        list((msg.org_context or {}).keys()),
        sorted((msg.patient_snapshot or {}).keys()),
        _short(sender), _state_summary(),
    )

    _pending_executor_detection[msg.pass_id] = sender
    ctx.logger.info(
        "[STATE] Registered detection pass_id=%s executor=…%s | %s",
        msg.pass_id, _short(sender), _state_summary(),
    )

    full_snapshot = msg.patient_snapshot or {}
    if not full_snapshot:
        ctx.logger.error(
            "[VALIDATE] Missing patient_snapshot pass_id=%s patient_id=%s domain=%s",
            msg.pass_id, msg.patient_id, _DOMAIN,
        )
    domain_context, parse_meta = parse_life_graph_for_domain(full_snapshot, _DOMAIN)
    domain_context_bytes = len(json.dumps(domain_context, default=str))
    ctx.logger.info(
        "[PARSE] pass_id=%s domain=%s kept_keys=%s dropped_keys=%s context_bytes=%s",
        msg.pass_id,
        _DOMAIN,
        parse_meta.get("kept_top_level_keys"),
        parse_meta.get("dropped_top_level_keys"),
        domain_context_bytes,
    )

    worker_snapshot_meta = {
        **(msg.snapshot_meta or {}),
        "supervisor_domain": _DOMAIN,
        "domain_parse_meta": parse_meta,
    }
    detection_for_worker = OnDemandDetectionRequest(
        patient_id=msg.patient_id,
        trigger=msg.trigger,
        pass_id=msg.pass_id,
        updated_domain=_DOMAIN,
        org_context=msg.org_context or {},
        patient_snapshot={},
        snapshot_meta=worker_snapshot_meta,
        domain_patient_context=domain_context,
    )
    _pending_detection_worker_request[msg.pass_id] = detection_for_worker
    _pending_detection_retry_count[msg.pass_id] = 0
    ctx.logger.info(
        "[ROUTE] Forwarding detection pass_id=%s patient_id=%s domain=%s "
        "context_keys=%s -> financial-worker …%s",
        msg.pass_id, msg.patient_id, _DOMAIN, sorted(domain_context.keys()),
        _short(FINANCIAL_WORKER_ADDRESS),
    )
    await ctx.send(FINANCIAL_WORKER_ADDRESS, detection_for_worker)


@supervisor.on_message(WorkerResult)
async def handle_worker_result(
    ctx: Context, worker_sender: str, result: WorkerResult
) -> None:
    if result.domain != _DOMAIN:
        ctx.logger.warning(
            "[RECV][IGNORE] WorkerResult pass_id=%s domain=%s expected=%s sender=…%s",
            result.pass_id, result.domain, _DOMAIN, _short(worker_sender),
        )
        return

    ctx.logger.info(
        "[RECV] WorkerResult pass_id=%s patient_id=%s domain=%s drafts=%d sender=…%s",
        result.pass_id, result.patient_id, result.domain, len(result.drafts),
        _short(worker_sender),
    )

    retry_msg = _pending_detection_worker_request.get(result.pass_id)
    known_recipient_emails = _known_recipient_emails_from_detection_request(retry_msg)
    validation_errors = _validate_detection_drafts_for_api_fields(
        result,
        known_recipient_emails=known_recipient_emails,
    )
    if validation_errors:
        retry_count = _pending_detection_retry_count.get(result.pass_id, 0)
        ctx.logger.warning(
            "[API-VALIDATE] pass_id=%s domain=%s retry=%d errors=%s",
            result.pass_id, _DOMAIN, retry_count, validation_errors,
        )
        if retry_count < _MAX_DETECTION_RETRY:
            if retry_msg is not None:
                next_retry = retry_count + 1
                _pending_detection_retry_count[result.pass_id] = next_retry
                correction_meta = {
                    **(retry_msg.snapshot_meta or {}),
                    "detection_correction": {
                        "attempt": next_retry,
                        "max_attempts": _MAX_DETECTION_RETRY,
                        "validation_errors": validation_errors,
                    },
                }
                resend_msg = retry_msg.copy(update={"snapshot_meta": correction_meta})
                ctx.logger.warning(
                    "[CORRECTION-REQUEST] pass_id=%s domain=%s attempt=%d -> financial-worker …%s",
                    result.pass_id, _DOMAIN, next_retry, _short(FINANCIAL_WORKER_ADDRESS),
                )
                await ctx.send(FINANCIAL_WORKER_ADDRESS, resend_msg)
                return

    dropped_action_ids = {
        str(entry.get("action_id"))
        for entry in validation_errors
        if entry.get("action_id")
    }
    drafts_to_persist = [
        draft for draft in result.drafts if draft.action_id not in dropped_action_ids
    ]
    if dropped_action_ids:
        ctx.logger.error(
            "[DRAFT-DROPPED] pass_id=%s domain=%s dropped=%s",
            result.pass_id, _DOMAIN, sorted(dropped_action_ids),
        )

    for i, draft in enumerate(drafts_to_persist):
        ctx.logger.info(
            "[DRAFT] %d/%d action_id=%s type=%s urgency=%s review_by=%s desc=%r",
            i + 1, len(drafts_to_persist),
            draft.action_id, draft.type, draft.urgency_level, draft.review_by,
            _trunc(draft.description, 80),
        )
        try:
            write_action(draft.dict())
            ctx.logger.info("[DB-WRITE] action_id=%s — ok", draft.action_id)
        except Exception as exc:
            ctx.logger.error("[DB-WRITE] action_id=%s — FAILED: %s", draft.action_id, exc)

    executor_address = _pending_executor_detection.pop(result.pass_id, None)
    if executor_address is None:
        _pending_detection_worker_request.pop(result.pass_id, None)
        _pending_detection_retry_count.pop(result.pass_id, None)
        ctx.logger.warning(
            "[STATE][MISS] No pending executor for pass_id=%s — dropping WorkerResult | %s",
            result.pass_id, _state_summary(),
        )
        return

    supervisor_result = SupervisorResult(
        pass_id=result.pass_id,
        patient_id=result.patient_id,
        domain=_DOMAIN,
        actions=drafts_to_persist,
    )
    _pending_detection_worker_request.pop(result.pass_id, None)
    _pending_detection_retry_count.pop(result.pass_id, None)
    ctx.logger.info(
        "[SEND] SupervisorResult pass_id=%s patient_id=%s actions=%d -> executor …%s | %s",
        result.pass_id, result.patient_id, len(drafts_to_persist),
        _short(executor_address), _state_summary(),
    )
    await ctx.send(executor_address, supervisor_result)


# ---------------------------------------------------------------------------
# Production: modification
# ---------------------------------------------------------------------------

@supervisor.on_message(ModificationRequest)
async def handle_modification_request(
    ctx: Context, sender: str, msg: ModificationRequest
) -> None:
    if msg.domain != _DOMAIN:
        ctx.logger.warning(
            "[RECV][IGNORE] ModificationRequest action_id=%s domain=%s expected=%s sender=…%s",
            msg.action_id, msg.domain, _DOMAIN, _short(sender),
        )
        return

    ctx.logger.info(
        "[RECV] ModificationRequest action_id=%s patient_id=%s action_type=%s "
        "instruction=%r sender=…%s | %s",
        msg.action_id, msg.patient_id, msg.action_type,
        _trunc(msg.modification_instruction, 100), _short(sender), _state_summary(),
    )

    try:
        set_modification_in_progress(msg.action_id, True)
        ctx.logger.info("[DB] set_modification_in_progress action_id=%s — ok", msg.action_id)
    except Exception as exc:
        ctx.logger.error("[DB] set_modification_in_progress action_id=%s — FAILED: %s",
                         msg.action_id, exc)

    _pending_executor_modification[msg.action_id] = sender
    ctx.logger.info(
        "[STATE] Registered modification action_id=%s executor=…%s | %s",
        msg.action_id, _short(sender), _state_summary(),
    )

    task = ModificationTask(
        action_id=msg.action_id,
        patient_id=msg.patient_id,
        domain=msg.domain,
        action_type=msg.action_type,
        current_draft=msg.current_draft,
        modification_instruction=msg.modification_instruction,
        requires_live_api=False,
        api_context=None,
    )
    ctx.logger.info(
        "[ROUTE] ModificationTask action_id=%s patient_id=%s -> financial-worker …%s",
        msg.action_id, msg.patient_id, _short(FINANCIAL_WORKER_ADDRESS),
    )
    await ctx.send(FINANCIAL_WORKER_ADDRESS, task)


@supervisor.on_message(ModificationDraft)
async def handle_modification_draft(
    ctx: Context, worker_sender: str, draft: ModificationDraft
) -> None:
    ctx.logger.info(
        "[RECV] ModificationDraft action_id=%s revised_len=%d changes=%r sender=…%s",
        draft.action_id, len(draft.revised_draft),
        _trunc(draft.changes_summary, 100), _short(worker_sender),
    )

    try:
        replace_draft(draft.action_id, draft.revised_draft)
        ctx.logger.info("[DB] replace_draft action_id=%s — ok", draft.action_id)
    except Exception as exc:
        ctx.logger.error("[DB] replace_draft action_id=%s — FAILED: %s", draft.action_id, exc)

    executor_address = _pending_executor_modification.pop(draft.action_id, None)
    if executor_address is None:
        ctx.logger.warning(
            "[STATE][MISS] No pending executor for modification action_id=%s — dropping | %s",
            draft.action_id, _state_summary(),
        )
        return

    mod_result = ModificationResult(
        action_id=draft.action_id,
        patient_id="",
        revised_draft=draft.revised_draft,
        changes_summary=draft.changes_summary,
    )
    ctx.logger.info(
        "[SEND] ModificationResult action_id=%s revised_preview=%r -> executor …%s | %s",
        draft.action_id, _trunc(draft.revised_draft, 80),
        _short(executor_address), _state_summary(),
    )
    await ctx.send(executor_address, mod_result)


# ---------------------------------------------------------------------------
# Production: question
# ---------------------------------------------------------------------------

@supervisor.on_message(QuestionRequest)
async def handle_question_request(
    ctx: Context, sender: str, msg: QuestionRequest
) -> None:
    if msg.domain != _DOMAIN:
        ctx.logger.warning(
            "[RECV][IGNORE] QuestionRequest action_id=%s domain=%s expected=%s sender=…%s",
            msg.action_id, msg.domain, _DOMAIN, _short(sender),
        )
        return

    ctx.logger.info(
        "[RECV] QuestionRequest action_id=%s patient_id=%s question=%r sender=…%s | %s",
        msg.action_id, msg.patient_id, _trunc(msg.question, 100),
        _short(sender), _state_summary(),
    )

    _pending_executor_question[msg.action_id] = sender
    ctx.logger.info(
        "[STATE] Registered question action_id=%s executor=…%s | %s",
        msg.action_id, _short(sender), _state_summary(),
    )

    # Fetch live patient data from the database
    patient_context = "{}"
    if msg.patient_id and msg.patient_id != "unknown":
        try:
            life_graph = serialize_life_graph(msg.patient_id)
            if life_graph:
                patient_context = json.dumps(life_graph, indent=2)
                ctx.logger.info(
                    "[DB] serialize_life_graph patient_id=%s — ok (keys=%s)",
                    msg.patient_id, list(life_graph.keys()),
                )
            else:
                ctx.logger.warning(
                    "[DB] serialize_life_graph patient_id=%s — no record found", msg.patient_id,
                )
        except Exception as exc:
            ctx.logger.error(
                "[DB] serialize_life_graph patient_id=%s — FAILED: %s", msg.patient_id, exc,
            )
    else:
        ctx.logger.warning(
            "[DB] Skipping life graph fetch — patient_id=%s is unknown", msg.patient_id,
        )

    task = QuestionTask(
        action_id=msg.action_id,
        patient_id=msg.patient_id,
        domain=msg.domain,
        question=msg.question,
        api_lookup_instruction=patient_context,
    )
    ctx.logger.info(
        "[ROUTE] QuestionTask action_id=%s patient_id=%s patient_data_len=%d -> financial-worker …%s",
        msg.action_id, msg.patient_id, len(patient_context), _short(FINANCIAL_WORKER_ADDRESS),
    )
    await ctx.send(FINANCIAL_WORKER_ADDRESS, task)


@supervisor.on_message(QuestionApiResult)
async def handle_question_api_result(
    ctx: Context, worker_sender: str, result: QuestionApiResult
) -> None:
    ctx.logger.info(
        "[RECV] QuestionApiResult action_id=%s answer_len=%d answer_preview=%r sender=…%s",
        result.action_id, len(result.api_data),
        _trunc(result.api_data, 100), _short(worker_sender),
    )

    executor_address = _pending_executor_question.pop(result.action_id, None)
    if executor_address is None:
        ctx.logger.warning(
            "[STATE][MISS] No pending executor for question action_id=%s — dropping | %s",
            result.action_id, _state_summary(),
        )
        return

    answer = QuestionAnswer(
        action_id=result.action_id,
        answer=result.api_data,
        requires_action=False,
        suggested_action=None,
    )
    ctx.logger.info(
        "[SEND] QuestionAnswer action_id=%s -> executor …%s | %s",
        result.action_id, _short(executor_address), _state_summary(),
    )
    await ctx.send(executor_address, answer)


if __name__ == "__main__":
    supervisor.run()
