"""Actions router — live SQLite-backed reads/writes."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.shared.api_capabilities import (
    build_execution_plan_preview,
    build_post_request_body,
    infer_primary_route_for_action,
    resolve_route_and_params_from_action,
)
from agents.shared.db import (
    get_action,
    get_action_rankings,
    get_chat_history,
    get_connection,
    get_pending_actions,
    update_action,
    write_chat_message,
)
from agents.shared.notifications import send_action_notification

router = APIRouter(prefix="/actions", tags=["actions"])

APPROVE_TIMEOUT_SECONDS = 12.0
EXECUTOR_INTERNAL_URL = os.getenv("EXECUTOR_INTERNAL_URL", "")
logger = logging.getLogger(__name__)


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


def _api_base() -> str:
    return os.getenv("MOCK_API_BASE", "http://localhost:8000").rstrip("/")


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class ActionModificationBody(BaseModel):
    idempotency_key: str | None = None
    modification_instruction: str | None = None
    reviewed: bool | None = None
    completed: bool | None = None
    urgency_level: str | None = None
    assigned_caregiver: str | None = None


def _enrich_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not actions:
        return actions
    patient_ids = list({a["patient_id"] for a in actions if a.get("patient_id")})
    if patient_ids:
        placeholders = ",".join("?" * len(patient_ids))
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT patient_id, name FROM patients WHERE patient_id IN ({placeholders})",
                patient_ids,
            ).fetchall()
        name_map = {row[0]: row[1] for row in rows}
    else:
        name_map = {}
    for a in actions:
        a.setdefault("patient_name", name_map.get(a.get("patient_id")))
        a.setdefault("is_overdue", a.get("is_overdue", 0))
        raw_schedule = a.get("schedule")
        if raw_schedule and isinstance(raw_schedule, str):
            try:
                a["schedule"] = json.loads(raw_schedule)
            except Exception:
                a["schedule"] = None
        else:
            a.setdefault("schedule", None)
        a["execution_plan"] = build_execution_plan_preview(a)
    return actions


@router.get("")
async def list_actions(
    sort: str = Query(default="rank", description="Sort order: 'rank' (urgency score) or 'created_at' (newest first)"),
    domain: str | None = Query(default=None),
    urgency: str | None = Query(default=None),
    type: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    is_overdue: bool | None = Query(default=None),
):
    try:
        if sort == "created_at":
            actions = get_pending_actions()
            actions.sort(key=lambda a: a.get("created_at") or "", reverse=True)
        else:
            actions = get_action_rankings()

        if domain is not None:
            actions = [a for a in actions if a.get("domain") == domain]
        if urgency is not None:
            actions = [a for a in actions if a.get("urgency_level") == urgency]
        if type is not None:
            actions = [a for a in actions if a.get("type") == type]
        if patient_id is not None:
            actions = [a for a in actions if a.get("patient_id") == patient_id]
        if is_overdue is not None:
            flag = 1 if is_overdue else 0
            actions = [a for a in actions if a.get("is_overdue") == flag]

        return ok(_enrich_actions(actions))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("/{action_id}")
async def fetch_action(action_id: str):
    try:
        action = get_action(action_id)
        if not action:
            return JSONResponse(status_code=404, content=err(f"Action {action_id!r} not found"))
        action["execution_plan"] = build_execution_plan_preview(action)
        return ok(action)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.patch("/{action_id}")
async def patch_action(action_id: str, body: ActionModificationBody):
    try:
        action = get_action(action_id)
        if not action:
            return JSONResponse(status_code=404, content=err(f"Action {action_id!r} not found"))

        # Idempotency check for modification_instruction
        if body.idempotency_key and body.modification_instruction:
            existing_payload = action.get("api_payload") or {}
            if isinstance(existing_payload, dict):
                if existing_payload.get("idempotency_key") == body.idempotency_key:
                    return ok(get_action(action_id))

        updates: dict = {}
        if body.reviewed is not None:
            updates["reviewed"] = int(body.reviewed)
        if body.completed is not None:
            updates["completed"] = int(body.completed)
        if body.urgency_level is not None:
            updates["urgency_level"] = body.urgency_level
        if body.assigned_caregiver is not None:
            updates["assigned_caregiver"] = body.assigned_caregiver
        if body.modification_instruction is not None:
            updates["modification_in_progress"] = 1
            if body.idempotency_key:
                updates["api_payload"] = {
                    "idempotency_key": body.idempotency_key,
                    "modification_instruction": body.modification_instruction,
                }

        if updates:
            update_action(action_id, updates)

        # Book the matching caregiver_schedule slot when assigning with a schedule
        if body.assigned_caregiver and action.get("schedule"):
            schedule = action["schedule"]
            if isinstance(schedule, str):
                try:
                    schedule = json.loads(schedule)
                except Exception:
                    schedule = None
            if schedule and schedule.get("start_time") and schedule.get("end_time"):
                with get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE caregiver_schedule SET booked=1
                        WHERE caregiver_id=? AND available=1 AND booked=0
                          AND start_time < ? AND end_time > ?
                        """,
                        (body.assigned_caregiver, schedule["end_time"], schedule["start_time"]),
                    )
                    conn.commit()

        if body.modification_instruction is not None and EXECUTOR_INTERNAL_URL:
            context_prefix = (
                f"[Action context] action_id={action_id} "
                f"patient_id={action.get('patient_id')} "
                f"domain={action.get('domain')} "
                f"type={action.get('type')}\n\n"
            )
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{EXECUTOR_INTERNAL_URL}/message",
                        json={"content": context_prefix + body.modification_instruction, "action_id": action_id},
                    )
            except httpx.HTTPError:
                pass  # DB write succeeded; agent delivery is best-effort

        updated = get_action(action_id)
        return ok(updated)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("/{action_id}/complete")
async def complete_action(action_id: str):
    try:
        action = get_action(action_id)
        if not action:
            return JSONResponse(status_code=404, content=err(f"Action {action_id!r} not found"))
        update_action(action_id, {"completed": 1})
        updated = get_action(action_id)
        return ok(updated)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("/{action_id}/dismiss")
async def dismiss_action(action_id: str):
    try:
        action = get_action(action_id)
        if not action:
            return JSONResponse(status_code=404, content=err(f"Action {action_id!r} not found"))
        update_action(action_id, {
            "completed": 1,
            "reviewed": 1,
            "completion_date": datetime.utcnow().isoformat(),
            "outcome": "dismissed",
        })
        updated = get_action(action_id)
        return ok(updated)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


class ChatMessageBody(BaseModel):
    message: str


@router.post("/{action_id}/chat")
async def action_chat(action_id: str, body: ChatMessageBody):
    if not EXECUTOR_INTERNAL_URL:
        return JSONResponse(status_code=503, content=err("executor_not_configured"))
    try:
        action = get_action(action_id)
        if not action:
            return JSONResponse(status_code=404, content=err(f"Action {action_id!r} not found"))
        chat_id = write_chat_message(action_id, "user", body.message)
        context_prefix = (
            f"[Action context] action_id={action_id} "
            f"patient_id={action.get('patient_id')} "
            f"domain={action.get('domain')} "
            f"type={action.get('type')}\n\n"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{EXECUTOR_INTERNAL_URL}/message",
                    json={"content": context_prefix + body.message, "action_id": action_id},
                )
        except httpx.HTTPError:
            return JSONResponse(status_code=502, content=err("executor_unavailable"))
        return ok({"status": "queued", "chat_id": chat_id})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("/{action_id}/chat-history")
async def action_chat_history(action_id: str):
    try:
        action = get_action(action_id)
        if not action:
            return JSONResponse(status_code=404, content=err(f"Action {action_id!r} not found"))
        return ok(get_chat_history(action_id))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


def _should_call_gmaps(action: dict[str, Any]) -> bool:
    if not _bool_env("ENABLE_GMAPS_ON_APPROVE", default=False):
        return False
    domain = str(action.get("domain") or "").strip().lower()
    if domain != "appointment":
        return False
    manual = str(action.get("manual_action_type") or "").strip().lower()
    return manual in {"transport", "caregiver_availability"}


def _build_execution_steps(action: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    route, route_params, route_errors, route_source = resolve_route_and_params_from_action(action)
    if route and route.startswith("POST /mock/"):
        method, path = route.split(" ", 1)
        steps.append(
            {
                "kind": "mock",
                "name": route,
                "method": method,
                "url": f"{_api_base()}{path}",
                "payload": build_post_request_body(route, route_params),
                "required": True,
                "route_errors": route_errors,
            }
        )

    if _should_call_gmaps(action):
        origins = route_params.get("origins")
        destinations = route_params.get("destinations")
        api_key = os.getenv("GOOGLE_MAPS_API_KEY") or ""
        if origins and destinations and api_key:
            steps.append(
                {
                    "kind": "gmaps",
                    "name": "GET gmaps:/maps/api/distancematrix/json",
                    "method": "GET",
                    "url": "https://maps.googleapis.com/maps/api/distancematrix/json",
                    "params": {
                        "origins": origins,
                        "destinations": destinations,
                        "key": api_key,
                    },
                    "required": False,
                }
            )

    recipient_email = action.get("recipient_email")
    if recipient_email:
        steps.append(
            {
                "kind": "email",
                "name": "POST resend:/emails",
                "required": True,
            }
        )

    logger.info(
        "[APPROVE][PLAN] action_id=%s domain=%s manual_action_type=%s route=%s route_source=%s route_errors=%s steps=%s",
        action.get("action_id"),
        action.get("domain"),
        action.get("manual_action_type"),
        route,
        route_source,
        route_errors,
        [step.get("name") for step in steps],
    )
    return steps


async def _execute_approved_action(
    action: dict[str, Any],
) -> dict[str, Any]:
    steps = _build_execution_steps(action)
    results: list[dict[str, Any]] = []

    if not steps:
        logger.info(
            "[APPROVE][SKIP] action_id=%s no external calls required",
            action.get("action_id"),
        )
        return {
            "success": True,
            "steps": [],
            "message": "No external API calls were required for this action.",
        }

    async with httpx.AsyncClient(timeout=APPROVE_TIMEOUT_SECONDS) as client:
        for step in steps:
            kind = step["kind"]
            if kind == "mock":
                preflight_errors = list(step.get("route_errors") or [])
                if preflight_errors:
                    results.append(
                        {
                            "step": step["name"],
                            "kind": kind,
                            "ok": False,
                            "error": "invalid_api_payload_template",
                            "details": preflight_errors,
                        }
                    )
                    logger.error(
                        "[APPROVE][MOCK] action_id=%s step=%s preflight_errors=%s",
                        action.get("action_id"),
                        step["name"],
                        preflight_errors,
                    )
                    continue
                try:
                    resp = await client.request(
                        method=step["method"],
                        url=step["url"],
                        json=step.get("payload") or {},
                    )
                    body: Any
                    try:
                        body = resp.json()
                    except Exception:
                        body = {"raw": resp.text[:800]}

                    ok_flag = 200 <= resp.status_code < 300
                    results.append(
                        {
                            "step": step["name"],
                            "kind": kind,
                            "ok": ok_flag,
                            "status_code": resp.status_code,
                            "response": body,
                        }
                    )
                    logger.info(
                        "[APPROVE][MOCK] action_id=%s step=%s status=%s ok=%s",
                        action.get("action_id"),
                        step["name"],
                        resp.status_code,
                        ok_flag,
                    )
                except Exception as exc:
                    results.append(
                        {
                            "step": step["name"],
                            "kind": kind,
                            "ok": False,
                            "error": str(exc),
                        }
                    )
                    logger.error(
                        "[APPROVE][MOCK] action_id=%s step=%s failed=%s",
                        action.get("action_id"),
                        step["name"],
                        exc,
                    )
                continue

            if kind == "gmaps":
                try:
                    resp = await client.get(step["url"], params=step.get("params") or {})
                    body: Any
                    try:
                        body = resp.json()
                    except Exception:
                        body = {"raw": resp.text[:800]}

                    results.append(
                        {
                            "step": step["name"],
                            "kind": kind,
                            "ok": 200 <= resp.status_code < 300,
                            "status_code": resp.status_code,
                            "response": body,
                        }
                    )
                    logger.info(
                        "[APPROVE][GMAPS] action_id=%s step=%s status=%s",
                        action.get("action_id"),
                        step["name"],
                        resp.status_code,
                    )
                except Exception as exc:
                    results.append(
                        {
                            "step": step["name"],
                            "kind": kind,
                            "ok": False,
                            "error": str(exc),
                        }
                    )
                    logger.error(
                        "[APPROVE][GMAPS] action_id=%s step=%s failed=%s",
                        action.get("action_id"),
                        step["name"],
                        exc,
                    )
                continue

            if kind == "email":
                subject = str(action.get("email_subject") or "").strip()
                if not subject:
                    results.append(
                        {
                            "step": step["name"],
                            "kind": kind,
                            "ok": False,
                            "error": "missing_email_subject",
                        }
                    )
                    logger.error(
                        "[APPROVE][EMAIL] action_id=%s missing email_subject",
                        action.get("action_id"),
                    )
                    continue
                body_text = action.get("draft_content") or action.get("description") or "Care action approved"
                body_html = f"<p>{escape(str(body_text))}</p>"
                email_result = send_action_notification(
                    action_id=str(action.get("action_id") or ""),
                    patient_id=str(action.get("patient_id") or ""),
                    recipient_email=str(action.get("recipient_email") or ""),
                    subject=subject,
                    body_html=body_html,
                )
                results.append(
                    {
                        "step": step["name"],
                        "kind": kind,
                        "ok": bool(email_result.get("sent")),
                        "response": email_result,
                    }
                )
                logger.info(
                    "[APPROVE][EMAIL] action_id=%s to=%s sent=%s",
                    action.get("action_id"),
                    action.get("recipient_email"),
                    email_result.get("sent"),
                )

    failed_required = [
        item
        for item, step in zip(results, steps)
        if step.get("required") and not item.get("ok")
    ]
    return {
        "success": not failed_required,
        "steps": results,
        "failed_required_steps": failed_required,
    }


def _merge_execution_payload(action: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    payload = action.get("api_payload")
    base = payload if isinstance(payload, dict) else {}
    return {
        **base,
        "approval_execution": execution,
        "approved_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.post("/{action_id}/approve")
async def approve_action(action_id: str):
    try:
        action = get_action(action_id)
        if not action:
            return JSONResponse(status_code=404, content=err(f"Action {action_id!r} not found"))

        logger.info(
            "[APPROVE][START] action_id=%s domain=%s manual_action_type=%s",
            action_id,
            action.get("domain"),
            action.get("manual_action_type"),
        )
        execution = await _execute_approved_action(action)
        updates: dict[str, Any] = {
            "reviewed": 1,
            "api_payload": _merge_execution_payload(action, execution),
        }
        if execution.get("success"):
            updates["completed"] = 1
            updates["completion_date"] = datetime.utcnow().isoformat()
            updates["outcome"] = "approved"
            if action.get("manual_action_type"):
                updates["scheduling_status"] = "completed"

        update_action(action_id, updates)
        updated = get_action(action_id)

        if execution.get("success"):
            logger.info("[APPROVE][DONE] action_id=%s success=true", action_id)
            return ok({"action": updated, "execution": execution})

        logger.warning("[APPROVE][DONE] action_id=%s success=false", action_id)
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "error": "Action approval finished with one or more required API failures.",
                "data": {"action": updated, "execution": execution},
            },
        )
    except Exception as exc:
        logger.exception("[APPROVE][FAIL] action_id=%s err=%s", action_id, exc)
        return JSONResponse(status_code=500, content=err(str(exc)))
