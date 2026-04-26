"""Patients router — live SQLite-backed reads/writes."""

from __future__ import annotations

import base64
import json as _json
from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.shared.db import (
    apply_patient_update,
    get_all_patients,
    get_connection,
    get_patient,
    get_patient_update,
    get_patient_update_history,
    get_pending_actions,
    serialize_complete_life_graph,
    serialize_life_graph,
    write_patient,
    write_patient_update,
)
from agents.shared.llm import call_claude_json, call_claude_vision

router = APIRouter(prefix="/patients", tags=["patients"])

_CLASSIFY_SYSTEM = """You are a patient record update classifier.
Given the current patient life graph (as context) and the update description,
return a JSON object with exactly these fields:
  domain (string: health | appointment | grocery | financial | scheduling | general),
  operation (string: update | add | remove),
  fields_changed (array of strings),
  summary (string, one sentence),
  proposed_changes (object: the exact fields and values to write to the patient record).
Return valid JSON only — no prose, no markdown fences."""

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_EXTRACT_VISION_PROMPT = (
    "Extract all patient record update information from this document and return a JSON object with: "
    "domain, operation, fields_changed (array), summary, proposed_changes (object). "
    "Return valid JSON only."
)


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


def _classify_update(patient_id: str, content: str) -> dict:
    from agents.shared.db import serialize_complete_life_graph
    graph = serialize_complete_life_graph(patient_id)
    system = _CLASSIFY_SYSTEM
    user = f"Current patient life graph:\n{_json.dumps(graph, indent=2)}\n\nUpdate description:\n{content}"
    return call_claude_json(system, user, max_tokens=1500)


async def _extract_text_from_update_file(file: UploadFile) -> str:
    content_type = (file.content_type or "").split(";")[0].strip()
    data = await file.read()

    if content_type == "application/pdf" or (file.filename or "").endswith(".pdf"):
        try:
            import pdfplumber  # type: ignore
        except ImportError:
            raise ImportError("pdfplumber")
        import io
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    if content_type in _IMAGE_TYPES or content_type.startswith("image/"):
        b64 = base64.b64encode(data).decode()
        result = call_claude_vision(b64, content_type, _EXTRACT_VISION_PROMPT)
        return f"__vision_classification__:{_json.dumps(result)}"

    if content_type.startswith("text/") or (file.filename or "").endswith(".txt"):
        return data.decode("utf-8", errors="replace")

    raise TypeError(content_type or "unknown")


class PatientBody(BaseModel):
    patient_id: str | None = None
    name: str | None = None
    age: int | None = None
    address: str | None = None
    preferences: dict | None = None
    active: int | None = None


class PatientUpdateBody(BaseModel):
    content: str
    caregiver_id: str | None = None


_URGENCY_ORDER = {"tier_0": 0, "tier_1": 1, "tier_2": 2, "tier_3": 3}


def _enrich_patient_list(patients: list[dict]) -> list[dict]:
    if not patients:
        return patients
    patient_ids = [p["patient_id"] for p in patients]
    placeholders = ",".join("?" * len(patient_ids))
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT a.patient_id,
                   COUNT(*) AS pending_action_count,
                   SUM(a.is_overdue) AS overdue_action_count,
                   a.urgency_level,
                   c.name AS assigned_caregiver_name
            FROM action_history a
            LEFT JOIN caregivers c ON c.caregiver_id = a.assigned_caregiver
            WHERE a.completed=0 AND a.patient_id IN ({placeholders})
            GROUP BY a.patient_id, a.urgency_level, c.name
            """,
            patient_ids,
        ).fetchall()

    from collections import defaultdict
    data: dict[str, dict] = defaultdict(lambda: {
        "pending_action_count": 0,
        "overdue_action_count": 0,
        "highest_urgency_level": None,
        "assigned_caregiver_name": None,
    })
    for row in rows:
        pid = row[0]
        data[pid]["pending_action_count"] += row[1] or 0
        data[pid]["overdue_action_count"] += row[2] or 0
        urgency = row[3]
        current = data[pid]["highest_urgency_level"]
        if urgency and (current is None or _URGENCY_ORDER.get(urgency, 99) < _URGENCY_ORDER.get(current, 99)):
            data[pid]["highest_urgency_level"] = urgency
        if row[4] and not data[pid]["assigned_caregiver_name"]:
            data[pid]["assigned_caregiver_name"] = row[4]

    for p in patients:
        pid = p["patient_id"]
        p.update(data[pid])
    return patients


@router.get("")
async def list_patients():
    try:
        return ok(_enrich_patient_list(get_all_patients()))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


def _get_action_history(patient_id: str) -> list[dict]:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM action_history WHERE patient_id=? AND completed=1 ORDER BY completion_date DESC LIMIT 50",
            (patient_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return [dict(zip(cols, row)) for row in rows]


@router.get("/{patient_id}")
async def fetch_patient(patient_id: str):
    try:
        if not get_patient(patient_id):
            return JSONResponse(status_code=404, content=err(f"Patient {patient_id!r} not found"))
        lg = serialize_life_graph(patient_id)
        pending_actions = get_pending_actions(patient_id)
        action_history = _get_action_history(patient_id)
        life_graph_json = {
            "health": {
                "medications": [
                    {"name": m.get("name"), "dose": m.get("dosage"), "frequency": m.get("frequency")}
                    for m in lg.get("medications", [])
                ],
            },
            "appointments": [
                {"date": a.get("next_scheduled"), "provider": a.get("provider"), "type": a.get("specialty")}
                for a in lg.get("appointments", [])
            ],
            "grocery": lg.get("grocery", {}),
            "financial": lg.get("financial", {}),
            "emergency_contacts": lg.get("emergency_contacts", []),
        }
        return ok({
            "patient_id": lg["patient_id"],
            "name": lg["name"],
            "age": lg.get("age"),
            "address": lg.get("address"),
            "preferences_json": lg.get("preferences", {}),
            "life_graph_json": life_graph_json,
            "assigned_caregivers": lg.get("assigned_caregivers", []),
            "pending_actions": pending_actions,
            "action_history": action_history,
        })
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("")
async def create_patient(body: PatientBody):
    try:
        data = body.model_dump(exclude_none=True)
        patient_id = write_patient(data)
        patient = get_patient(patient_id)
        return ok(patient)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.put("/{patient_id}")
async def update_patient(patient_id: str, body: PatientBody):
    try:
        data = body.model_dump(exclude_none=True)
        data["patient_id"] = patient_id
        write_patient(data)
        patient = get_patient(patient_id)
        return ok(patient)
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("/{patient_id}/update")
async def propose_patient_update(patient_id: str, body: PatientUpdateBody):
    try:
        patient = get_patient(patient_id)
        if not patient:
            return JSONResponse(status_code=404, content=err(f"Patient {patient_id!r} not found"))
        classification = _classify_update(patient_id, body.content)
        update_id = write_patient_update({
            "patient_id": patient_id,
            "caregiver_id": body.caregiver_id,
            "domain": classification.get("domain"),
            "operation": classification.get("operation"),
            "fields_changed": classification.get("fields_changed", []),
            "summary": classification.get("summary"),
            "proposed_changes": classification.get("proposed_changes"),
            "confirmed": 0,
            "applied": 0,
        })
        return ok({"requires_confirmation": True, "update_id": update_id, "classification": classification})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("/{patient_id}/update/{update_id}/confirm")
async def confirm_patient_update(patient_id: str, update_id: int):
    from api.routers.ingest import _trigger_detect
    try:
        update = get_patient_update(update_id)
        if not update:
            return JSONResponse(status_code=404, content=err(f"Update {update_id} not found"))
        if update.get("applied"):
            return JSONResponse(status_code=409, content=err("Update already applied"))
        apply_patient_update(update_id, update.get("proposed_changes") or {})
        detect_status = await _trigger_detect(
            patient_id, "patient_update", update.get("domain")
        )
        return ok({"applied": True, "patient_id": patient_id, "update_id": update_id, "detect_status": detect_status})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.post("/{patient_id}/update/file")
async def propose_patient_update_file(
    patient_id: str,
    file: UploadFile,
    caregiver_id: Annotated[str | None, Form()] = None,
):
    try:
        patient = get_patient(patient_id)
        if not patient:
            return JSONResponse(status_code=404, content=err(f"Patient {patient_id!r} not found"))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))

    try:
        raw = await _extract_text_from_update_file(file)
    except ImportError:
        return JSONResponse(status_code=501, content=err("pdfplumber is not installed; PDF ingest unavailable"))
    except TypeError as exc:
        return JSONResponse(status_code=415, content=err(f"Unsupported file type: {exc}"))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))

    try:
        if raw.startswith("__vision_classification__:"):
            classification = _json.loads(raw[len("__vision_classification__:"):])
        else:
            classification = _classify_update(patient_id, raw)

        update_id = write_patient_update({
            "patient_id": patient_id,
            "caregiver_id": caregiver_id,
            "domain": classification.get("domain"),
            "operation": classification.get("operation"),
            "fields_changed": classification.get("fields_changed", []),
            "summary": classification.get("summary"),
            "proposed_changes": classification.get("proposed_changes"),
            "confirmed": 0,
            "applied": 0,
        })
        return ok({"requires_confirmation": True, "update_id": update_id, "classification": classification})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("/{patient_id}/update-history")
async def patient_update_history(patient_id: str):
    try:
        return ok(get_patient_update_history(patient_id))
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))
