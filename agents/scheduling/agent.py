"""Scheduling agent scaffold."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from uagents import Agent, Context

from agents.shared.api_capabilities import worker_api_capability_block
from agents.shared.config import SCHEDULING_AGENT_SEED, LocalFirstResolver
from agents.shared.constants import AGENT_PORTS
from agents.shared.db import get_action, update_action, write_notification
from agents.shared.models import (
    MockDomainTask,
    MockSupervisorResult,
    SchedulingOptions,
    SchedulingQuery,
)

_MOCK_API_BASE = os.getenv("MOCK_API_BASE", "http://localhost:8000").rstrip("/")

# Keyed by action_id -> {options: list, requester_address: str}
_pending_sessions: dict[str, dict] = {}

agent = Agent(
    name="scheduling-agent",
    seed=SCHEDULING_AGENT_SEED,
    port=AGENT_PORTS["scheduling_agent"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=str(Path(__file__).parent / "README.md"),
    resolve=LocalFirstResolver(),
)

_SCHEDULING_API_GUIDANCE = worker_api_capability_block("scheduling")


@agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info("[API-GUIDANCE] scheduling capability schema loaded:\n%s", _SCHEDULING_API_GUIDANCE)


@agent.on_message(MockDomainTask)
async def handle_task(ctx: Context, sender: str, task: MockDomainTask) -> None:
    if task.domain != "scheduling":
        ctx.logger.warning(
            "Ignoring MockDomainTask request_id=%s domain=%s expected=scheduling sender=%s",
            task.request_id,
            task.domain,
            sender,
        )
        return
    ctx.logger.info(
        "Received MockDomainTask request_id=%s domain=%s sender=%s",
        task.request_id,
        task.domain,
        sender,
    )
    response = MockSupervisorResult(
        request_id=task.request_id,
        domain="scheduling",
        supervisor="scheduling-agent",
        result=f"Scheduling mock complete: matched options for '{task.query}'",
    )
    ctx.logger.info(
        "Sending MockSupervisorResult request_id=%s back to sender=%s",
        task.request_id,
        sender,
    )
    await ctx.send(sender, response)


@agent.on_message(SchedulingQuery)
async def handle_scheduling_query(ctx: Context, sender: str, msg: SchedulingQuery) -> None:
    ctx.logger.info(
        "Received SchedulingQuery action_id=%s patient_id=%s sender=%s",
        msg.action_id,
        msg.patient_id,
        sender,
    )
    today = datetime.now(timezone.utc).date().isoformat()
    params = {
        "date": today,
        "manual_action_type": "caregiver_scheduling",
        "patient_id": msg.patient_id,
        "duration_hours": 2.0,
    }
    options: list = []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{_MOCK_API_BASE}/mock/caregivers/available", params=params)
            resp.raise_for_status()
            data = resp.json()
            options = data if isinstance(data, list) else data.get("options", [])
    except Exception as exc:
        ctx.logger.error("Failed to fetch caregiver availability: %s", exc)

    if options:
        scheduling_status = "pending_approval"
        _pending_sessions[msg.action_id] = {
            "options": options,
            "requester_address": msg.requester_address,
        }
    else:
        scheduling_status = "no_availability"

    update_action(msg.action_id, {
        "caregiver_options_json": options,
        "scheduling_status": scheduling_status,
    })

    await ctx.send(
        msg.requester_address,
        SchedulingOptions(action_id=msg.action_id, options=options),
    )
    ctx.logger.info(
        "Sent SchedulingOptions action_id=%s options_count=%d status=%s",
        msg.action_id,
        len(options),
        scheduling_status,
    )


def handle_scheduling_selection(action_id: str, choice: str) -> dict:
    """Handle caregiver selection from the chat interface.

    Args:
        action_id: The action to update.
        choice: Numeric string "1"-"N" selecting from the options list, or "cancel".

    Returns:
        Result dict with keys: status, message, and optionally caregiver.
    """
    session = _pending_sessions.get(action_id)
    if session is None:
        return {"status": "error", "message": f"No pending session for action_id={action_id}"}

    options = session["options"]

    if choice.strip().lower() == "cancel":
        update_action(action_id, {"scheduling_status": "cancelled"})
        action = get_action(action_id)
        patient_id = action.get("patient_id", "")
        write_notification(
            type="scheduling",
            action_id=action_id,
            patient_id=patient_id,
            title="Scheduling Cancelled",
            body=f"Caregiver scheduling for action {action_id} was cancelled by the user.",
        )
        _pending_sessions.pop(action_id, None)
        return {"status": "cancelled", "message": "Scheduling cancelled."}

    try:
        idx = int(choice.strip()) - 1
    except ValueError:
        return {"status": "error", "message": f"Invalid choice '{choice}'. Use a number 1-{len(options)} or 'cancel'."}

    if idx < 0 or idx >= len(options):
        return {"status": "error", "message": f"Choice {choice} out of range. Valid range: 1-{len(options)}."}

    selected = options[idx]
    caregiver_id = selected.get("caregiver_id") or selected.get("id", "")
    caregiver_name = selected.get("name", caregiver_id)

    action = get_action(action_id)
    patient_id = action.get("patient_id", "")
    date = selected.get("date", datetime.now(timezone.utc).date().isoformat())
    start_time = selected.get("start_time", "")

    try:
        resp = httpx.post(
            f"{_MOCK_API_BASE}/mock/caregivers/book",
            json={
                "caregiver_id": caregiver_id,
                "patient_id": patient_id,
                "action_id": action_id,
                "date": date,
                "start_time": start_time,
            },
            timeout=8.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        return {"status": "error", "message": f"Booking request failed: {exc}"}

    update_action(action_id, {
        "scheduling_status": "unconfirmed",
        "assigned_caregiver": caregiver_id,
    })
    write_notification(
        type="scheduling",
        action_id=action_id,
        patient_id=patient_id,
        title="Caregiver Booked (Pending Confirmation)",
        body=f"Caregiver {caregiver_name} booked for action {action_id}. Awaiting confirmation.",
    )
    _pending_sessions.pop(action_id, None)
    return {"status": "booked", "message": f"Caregiver {caregiver_name} booked.", "caregiver": selected}


def handle_scheduling_decline(action_id: str) -> dict:
    """Handle decline / release of an assigned caregiver.

    Releases the caregiver via the mock API, resets scheduling state, and
    writes an ExpirationEscalation notification so the supervisor can re-schedule.

    Returns:
        Result dict with keys: status and message.
    """
    action = get_action(action_id)
    if not action:
        return {"status": "error", "message": f"Action {action_id} not found."}

    assigned_caregiver = action.get("assigned_caregiver") or ""
    patient_id = action.get("patient_id", "")

    if assigned_caregiver:
        try:
            resp = httpx.post(
                f"{_MOCK_API_BASE}/mock/caregivers/release",
                json={"caregiver_id": assigned_caregiver, "action_id": action_id},
                timeout=8.0,
            )
            resp.raise_for_status()
        except Exception as exc:
            return {"status": "error", "message": f"Release request failed: {exc}"}

    update_action(action_id, {
        "assigned_caregiver": None,
        "scheduling_status": "pending_approval",
    })
    write_notification(
        type="escalation",
        action_id=action_id,
        patient_id=patient_id,
        title="Scheduling Declined – Re-scheduling Required",
        body=(
            f"Caregiver assignment for action {action_id} was declined. "
            "Caregiver released and action returned to pending approval."
        ),
    )
    return {"status": "released", "message": "Caregiver released. Action reset to pending_approval."}


if __name__ == "__main__":
    agent.run()
