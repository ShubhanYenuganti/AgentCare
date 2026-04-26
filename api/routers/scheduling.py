"""Scheduling router — live SQLite-backed reads/writes."""

from __future__ import annotations

from datetime import datetime

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.shared.db import (
    book_caregiver_slot,
    get_action,
    get_scheduling_tasks,
    update_action,
    write_notification,
)

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


class BookingBody(BaseModel):
    caregiver_id: str
    date: str


class AssignBody(BaseModel):
    caregiver_id: str


@router.get("/tasks")
async def list_scheduling_tasks():
    try:
        return ok(get_scheduling_tasks())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("/book")
async def book_slot(body: BookingBody):
    try:
        book_caregiver_slot(body.caregiver_id, body.date)
        return ok({"caregiver_id": body.caregiver_id, "date": body.date, "booked": True})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("/{action_id}/assign")
async def assign_caregiver(action_id: str, body: AssignBody):
    action = get_action(action_id)
    if not action:
        return JSONResponse(status_code=404, content=err("Action not found"))
    if action.get("scheduling_status") != "pending_approval":
        return JSONResponse(status_code=409, content=err("Action is not pending approval"))
    update_action(action_id, {
        "assigned_caregiver": body.caregiver_id,
        "scheduling_status": "unconfirmed",
    })
    return ok(get_action(action_id))


@router.post("/{action_id}/confirm")
async def confirm_action(action_id: str):
    action = get_action(action_id)
    if not action:
        return JSONResponse(status_code=404, content=err("Action not found"))
    if action.get("scheduling_status") != "unconfirmed":
        return JSONResponse(status_code=409, content=err("Action is not in unconfirmed state"))
    update_action(action_id, {
        "scheduling_status": "confirmed",
        "completed": 1,
        "completion_date": datetime.utcnow().isoformat(),
    })
    write_notification(
        type="confirmation",
        action_id=action_id,
        patient_id=action.get("patient_id", ""),
        title="Action Confirmed",
        body=f"Action {action_id} has been confirmed and completed.",
    )
    return ok(get_action(action_id))


@router.post("/{action_id}/cancel")
async def cancel_action(action_id: str):
    action = get_action(action_id)
    if not action:
        return JSONResponse(status_code=404, content=err("Action not found"))
    current_status = action.get("scheduling_status")
    if current_status not in ("pending_approval", "unconfirmed"):
        return JSONResponse(
            status_code=409,
            content=err(f"Cannot cancel action with scheduling_status='{current_status}'"),
        )
    update_action(action_id, {
        "assigned_caregiver": "",
        "scheduling_status": "cancelled",
    })
    write_notification(
        type="cancellation",
        action_id=action_id,
        patient_id=action.get("patient_id", ""),
        title="Scheduling Cancelled",
        body=f"Scheduling for action {action_id} was cancelled.",
    )
    return ok(get_action(action_id))


@router.post("/{action_id}/decline")
async def decline_action(action_id: str):
    action = get_action(action_id)
    if not action:
        return JSONResponse(status_code=404, content=err("Action not found"))
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(
                "http://localhost:8000/mock/caregivers/release",
                json={"action_id": action_id, "caregiver_id": action.get("assigned_caregiver", "")},
            )
    except Exception:
        pass
    update_action(action_id, {
        "assigned_caregiver": "",
        "scheduling_status": "pending_approval",
    })
    write_notification(
        type="escalation",
        action_id=action_id,
        patient_id=action.get("patient_id", ""),
        title="Action Declined — Reassignment Needed",
        body=f"Action {action_id} was declined by the assigned caregiver and needs reassignment.",
    )
    return ok(get_action(action_id))
