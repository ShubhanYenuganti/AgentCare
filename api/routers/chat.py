"""General chat router — session-scoped freeform chat backed by executor pipeline."""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.shared.db import (
    commit_staged_to_action_history,
    create_session,
    get_session_messages,
    get_staged_action,
    session_exists,
    update_staged_action_payload,
    update_staged_action_status,
    write_chat_session_message,
    write_staged_action,
)

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

EXECUTOR_INTERNAL_URL = os.getenv("EXECUTOR_INTERNAL_URL", "")
EXECUTOR_TIMEOUT = 60.0


def ok(data: Any) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


class SendMessageBody(BaseModel):
    session_id: str | None = None
    message: str


class ModifyDraftBody(BaseModel):
    feedback: str


def _format_message(row: dict) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "stage": row.get("stage") or "",
        "intent_class": row.get("intent_class"),
        "domain": row.get("domain"),
        "patient_ids": row.get("patient_ids") or [],
        "draft_action_id": row.get("draft_action_id"),
        "created_at": row.get("created_at"),
    }


@router.post("")
async def send_message(body: SendMessageBody):
    if not body.message or not body.message.strip():
        return JSONResponse(status_code=400, content=err("message is required"))

    session_id = body.session_id
    if session_id:
        if not session_exists(session_id):
            return JSONResponse(status_code=404, content=err(f"Session {session_id!r} not found"))
    else:
        session_id = str(uuid4())
        create_session(session_id)

    write_chat_session_message(session_id, "user", body.message)
    prior_messages = get_session_messages(session_id)

    if not EXECUTOR_INTERNAL_URL:
        logger.warning("EXECUTOR_INTERNAL_URL not set; returning stub reply")
        reply_content = "[Executor not configured] " + body.message
        write_chat_session_message(session_id, "agent", reply_content, stage="answered")
        return ok({"session_id": session_id, "reply": reply_content, "stage": "answered", "draft_action_id": None})

    try:
        async with httpx.AsyncClient(timeout=EXECUTOR_TIMEOUT) as client:
            resp = await client.post(
                f"{EXECUTOR_INTERNAL_URL}/general-chat",
                json={"session_id": session_id, "messages": prior_messages},
            )
        if resp.status_code != 200:
            logger.error("Executor /general-chat returned %s: %s", resp.status_code, resp.text)
            return JSONResponse(status_code=502, content=err("executor_error"))
        data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("Executor unreachable: %s", exc)
        return JSONResponse(status_code=502, content=err("executor_unavailable"))

    reply = data.get("reply", "")
    stage = data.get("stage", "answered")
    draft_action_id = data.get("draft_action_id")
    intent_class = data.get("intent_class")
    domain = data.get("domain")
    patient_ids = data.get("patient_ids") or []

    write_chat_session_message(
        session_id,
        "agent",
        reply,
        stage=stage,
        intent_class=intent_class,
        domain=domain,
        patient_ids=patient_ids,
        draft_action_id=draft_action_id,
    )

    return ok({
        "session_id": session_id,
        "reply": reply,
        "stage": stage,
        "draft_action_id": draft_action_id,
        "intent_class": intent_class,
        "domain": domain,
    })


@router.get("/history")
async def get_history(session_id: str):
    if not session_exists(session_id):
        return JSONResponse(status_code=404, content=err(f"Session {session_id!r} not found"))
    messages = get_session_messages(session_id)
    return ok([_format_message(m) for m in messages])


@router.post("/action/{draft_action_id}/approve")
async def approve_draft(draft_action_id: str):
    staged = get_staged_action(draft_action_id)
    if not staged or staged.get("status") != "pending_approval":
        return JSONResponse(status_code=404, content=err("Draft not found or not pending approval"))
    try:
        action_id = commit_staged_to_action_history(draft_action_id)
    except Exception as exc:
        logger.error("commit_staged_to_action_history failed: %s", exc)
        return JSONResponse(status_code=500, content=err(str(exc)))
    return ok({"action_id": action_id})


@router.post("/action/{draft_action_id}/discard")
async def discard_draft(draft_action_id: str):
    staged = get_staged_action(draft_action_id)
    if not staged:
        return JSONResponse(status_code=404, content=err("Draft not found"))
    update_staged_action_status(draft_action_id, "discarded")
    return ok({"status": "discarded"})


@router.post("/action/{draft_action_id}/modify")
async def modify_draft(draft_action_id: str, body: ModifyDraftBody):
    staged = get_staged_action(draft_action_id)
    if not staged or staged.get("status") != "pending_approval":
        return JSONResponse(status_code=404, content=err("Draft not found or not pending approval"))

    if not EXECUTOR_INTERNAL_URL:
        return JSONResponse(status_code=503, content=err("executor_not_configured"))

    session_id = staged.get("session_id", "")
    original_draft = staged["draft_payload"]

    try:
        async with httpx.AsyncClient(timeout=EXECUTOR_TIMEOUT) as client:
            resp = await client.post(
                f"{EXECUTOR_INTERNAL_URL}/general-chat/revise",
                json={
                    "original_draft": original_draft,
                    "feedback": body.feedback,
                    "session_id": session_id,
                },
            )
        if resp.status_code != 200:
            return JSONResponse(status_code=502, content=err("executor_error"))
        data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("Executor unreachable on revise: %s", exc)
        return JSONResponse(status_code=502, content=err("executor_unavailable"))

    revised_payload = data.get("revised_draft")
    reply = data.get("reply", "")

    if revised_payload:
        update_staged_action_payload(draft_action_id, revised_payload)

    write_chat_session_message(
        session_id,
        "agent",
        reply,
        stage="draft_ready",
        draft_action_id=draft_action_id,
    )

    return ok({"reply": reply, "draft_action_id": draft_action_id})
