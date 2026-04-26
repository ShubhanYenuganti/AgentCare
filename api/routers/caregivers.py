"""Caregivers router — live SQLite-backed reads."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from agents.shared.db import (
    create_caregiver,
    get_all_caregivers,
    get_caregiver,
    get_caregiver_assignments,
    get_caregiver_available_slots,
    get_caregiver_schedule,
)


class DaySchedule(BaseModel):
    start: str
    end: str


class CreateCaregiverBody(BaseModel):
    name: str
    email: str
    phone: str
    role: str = "caregiver"
    schedule: dict[str, DaySchedule] = {}

router = APIRouter(prefix="/caregivers", tags=["caregivers"])


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


@router.post("")
async def add_caregiver(body: CreateCaregiverBody):
    try:
        schedule_dicts = {day: {"start": s.start, "end": s.end} for day, s in body.schedule.items()}
        caregiver_id = create_caregiver(
            name=body.name,
            email=body.email,
            phone=body.phone,
            role=body.role,
            schedule=schedule_dicts,
        )
        return ok({"caregiver_id": caregiver_id, "name": body.name, "email": body.email, "phone": body.phone, "role": body.role})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("/slots")
async def available_slots(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    try:
        slots = get_caregiver_available_slots(date)
        return ok(slots)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("")
async def list_caregivers():
    try:
        return ok(get_all_caregivers())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("/{caregiver_id}")
async def fetch_caregiver(caregiver_id: str):
    try:
        caregiver = get_caregiver(caregiver_id)
        if not caregiver:
            return JSONResponse(
                status_code=404, content=err(f"Caregiver {caregiver_id!r} not found")
            )
        return ok(caregiver)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("/{caregiver_id}/schedule")
async def caregiver_schedule(caregiver_id: str):
    try:
        today = date.today()
        start_date = today.isoformat()
        end_date = (today + timedelta(days=14)).isoformat()
        return ok(get_caregiver_schedule(caregiver_id, start_date, end_date))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("/{caregiver_id}/assignments")
async def caregiver_assignments(caregiver_id: str):
    try:
        return ok(get_caregiver_assignments(caregiver_id))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))
