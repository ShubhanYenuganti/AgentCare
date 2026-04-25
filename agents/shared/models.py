"""Shared message contracts for the mock scaffold."""

from __future__ import annotations

from typing import Any

from uagents import Model


class OnDemandDetectionRequest(Model):
    """Executor -> Domain Supervisor trigger model from Sprint 1 spec."""

    patient_id: str
    trigger: str
    pass_id: str
    updated_domain: str | None
    org_context: dict[str, Any]


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
    api_lookup_instruction: str


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
