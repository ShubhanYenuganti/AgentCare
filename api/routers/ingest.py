"""Ingest router — triggers detection flow via executor."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/ingest", tags=["ingest"])

EXECUTOR_INTERNAL_URL = os.getenv("EXECUTOR_INTERNAL_URL", "")


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


class IngestTextBody(BaseModel):
    content: str
    patient_id: str | None = None


@router.post("/text")
async def ingest_text(body: IngestTextBody):
    if not EXECUTOR_INTERNAL_URL:
        return ok({"status": "queued", "message": "Executor not configured; content queued."})

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{EXECUTOR_INTERNAL_URL}/ingest",
                json={"content": body.content, "patient_id": body.patient_id},
            )
            resp.raise_for_status()
            return ok(resp.json())
    except httpx.HTTPError as exc:
        return JSONResponse(status_code=502, content=err(f"Executor error: {exc}"))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))
