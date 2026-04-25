"""Caregivers router — live SQLite-backed reads."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from agents.shared.db import get_all_caregivers, get_caregiver, get_caregiver_available_slots

router = APIRouter(prefix="/caregivers", tags=["caregivers"])


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


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
