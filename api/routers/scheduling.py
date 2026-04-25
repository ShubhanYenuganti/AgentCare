"""Scheduling router — live SQLite-backed reads/writes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.shared.db import book_caregiver_slot, get_scheduling_tasks

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


class BookingBody(BaseModel):
    caregiver_id: str
    date: str


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
