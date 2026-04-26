"""Notifications router — live SQLite-backed reads/writes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agents.shared.db import get_unread_notifications, mark_notification_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


@router.get("")
async def list_notifications():
    try:
        return ok(get_unread_notifications())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("/{notification_id}/read")
async def mark_read(notification_id: int):
    try:
        mark_notification_read(notification_id)
        return ok(None)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))
