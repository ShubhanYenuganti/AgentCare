"""Shared message contracts for the MACOS multi-agent scaffold (Sprint 1 + Sprint 2)."""

from __future__ import annotations

from typing import Any, Literal

from uagents import Model

# ---------------------------------------------------------------------------
# Intent routing (Sprint 2)
# ---------------------------------------------------------------------------

IntentClass = Literal["question", "modification", "scheduling", "detection"]


class IntentRoutingResult(Model):
    """Output of the executor intent classifier."""

    intent: IntentClass
    domain: str | None  # None for broad detection/scheduling; set for single-domain detection
    confidence: str  # "high" | "low"
    trigger: str | None  # for detection: "patient_create" | "patient_update"
    updated_fields: list[str] | None  # for patient_update pre-filter


class DomainFanOutResult(Model):
    """Per-domain outcome from a detection fan-out pass."""

    domain: str
    success: bool
    actions: list[Any]  # list[ActionDraft] serialised
    error: str | None
    timed_out: bool


class DetectionFanOutResult(Model):
    """Aggregated result from a parallel detection fan-out (returned to executor)."""

    pass_id: str
    patient_id: str
    domain_results: list[DomainFanOutResult]
    partial: bool  # True if at least one domain timed out or failed


class ExecutorErrorPayload(Model):
    """Structured error returned from executor to ASI:One on failure."""

    request_id: str
    error_class: str  # "timeout" | "validation" | "downstream" | "internal"
    message: str
    domain: str | None


class OnDemandDetectionRequest(Model):
    """Executor -> Domain Supervisor trigger model from Sprint 1 spec."""

    patient_id: str
    trigger: str
    pass_id: str
    updated_domain: str | None
    org_context: dict[str, Any]
    patient_snapshot: dict[str, Any]
    snapshot_meta: dict[str, Any] | None = None
    domain_patient_context: dict[str, Any] | None = None


class ActionDraft(Model):
    """Domain Worker -> Domain Supervisor. One draft action."""

    action_id: str
    patient_id: str
    domain: str
    type: str
    description: str
    draft_content: str | None
    urgency_level: str
    review_by: str
    manual_action_type: str | None
    api_payload: dict[str, Any] | None
    recipient_email: str | None
    recipient_type: str | None
    email_subject: str | None = None


class WorkerResult(Model):
    """Domain Worker -> Domain Supervisor. All drafts from one detection pass."""

    pass_id: str
    patient_id: str
    domain: str
    drafts: list[ActionDraft]


class SupervisorResult(Model):
    """Domain Supervisor -> Executor. Risk-scored, framed, DB-written actions."""

    pass_id: str
    patient_id: str
    domain: str
    actions: list[ActionDraft]


class SchedulingQuery(Model):
    """Executor -> Scheduling Agent."""

    action_id: str
    patient_id: str
    manual_action_type: str
    description: str
    required_date: str | None
    requester_address: str


class SchedulingOptions(Model):
    """Scheduling Agent -> Executor / ASI:One."""

    action_id: str
    options: list[dict[str, Any]]


class ModificationRequest(Model):
    """Executor -> Health Supervisor."""

    action_id: str
    patient_id: str
    domain: str
    action_type: str
    current_draft: str
    modification_instruction: str
    life_graph_snapshot: str


class ModificationTask(Model):
    """Health Supervisor -> Health Worker."""

    action_id: str
    patient_id: str
    domain: str
    action_type: str
    current_draft: str
    modification_instruction: str
    requires_live_api: bool
    api_context: str | None


class ModificationDraft(Model):
    """Health Worker -> Health Supervisor."""

    action_id: str
    revised_draft: str
    changes_summary: str


class ModificationResult(Model):
    """Health Supervisor -> Executor."""

    action_id: str
    patient_id: str
    revised_draft: str
    changes_summary: str


class QuestionRequest(Model):
    """Executor -> Domain Supervisor."""

    action_id: str
    patient_id: str
    domain: str
    action_type: str
    question: str
    current_draft: str | None
    life_graph_snapshot: str


class QuestionTask(Model):
    """Domain Supervisor -> Domain Worker."""

    action_id: str
    patient_id: str
    domain: str
    question: str
    api_lookup_instruction: str = ""


class QuestionApiResult(Model):
    """Domain Worker -> Domain Supervisor."""

    action_id: str
    api_data: str


class QuestionAnswer(Model):
    """Domain Supervisor -> Executor."""

    action_id: str
    answer: str
    requires_action: bool
    suggested_action: str | None


class ExpirationEscalation(Model):
    action_id: str
    patient_id: str
    description: str
    urgency_level: str
    assigned_caregiver: str | None
    action_type: str


class MockDomainTask(Model):
    """Executor -> Supervisor -> Worker."""

    request_id: str
    domain: str
    query: str
    user_sender_address: str | None = None
    metadata: dict[str, Any] | None = None


class MockWorkerResult(Model):
    """Worker -> Supervisor."""

    request_id: str
    domain: str
    worker: str
    result: str


class MockSupervisorResult(Model):
    """Supervisor/Scheduling -> Executor."""

    request_id: str
    domain: str
    supervisor: str
    result: str
