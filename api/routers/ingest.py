"""Ingest router — LLM-extraction-based patient onboarding."""

from __future__ import annotations

import base64
import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.shared.db import write_patient
from agents.shared.llm import call_claude_json, call_claude_vision

router = APIRouter(prefix="/ingest", tags=["ingest"])

EXECUTOR_INTERNAL_URL = os.getenv("EXECUTOR_INTERNAL_URL", "")

_EXTRACT_SYSTEM = """You are a patient intake assistant.
Extract patient information from the provided text and return a JSON object with these fields
(include only fields that are present in the text):
  patient_id (optional override), name, age, address, preferences (object with any relevant details).
You MUST return valid JSON only — no prose, no markdown fences."""


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


def _extract_patient_from_text(text: str, patient_id_override: str | None) -> dict:
    result = call_claude_json(_EXTRACT_SYSTEM, text, max_tokens=1500)
    if not result.get("name") and not result.get("patient_id"):
        raise ValueError(repr(result))
    if patient_id_override:
        result["patient_id"] = patient_id_override
    return result


async def _trigger_detect(
    patient_id: str, trigger: str, updated_domain: str | None = None
) -> str:
    if not EXECUTOR_INTERNAL_URL:
        return "skipped"
    payload: dict = {"patient_id": patient_id, "trigger": trigger}
    if updated_domain:
        payload["updated_domain"] = updated_domain
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{EXECUTOR_INTERNAL_URL}/internal/detect", json=payload
            )
            resp.raise_for_status()
        return "triggered"
    except Exception:
        return "skipped"


class IngestTextBody(BaseModel):
    content: str
    patient_id: str | None = None
    context: str | None = None


@router.post("/text")
async def ingest_text(body: IngestTextBody):
    combined = (
        f"{body.context}\n\n{body.content}" if body.context else body.content
    )
    try:
        extracted = _extract_patient_from_text(combined, body.patient_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": "extraction_failed", "raw": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))

    try:
        patient_id = write_patient(extracted)
        detect_status = await _trigger_detect(patient_id, "patient_create")
        return ok({"patient_id": patient_id, "extracted": extracted, "detect_status": detect_status})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_EXTRACT_VISION_PROMPT = (
    "Extract all patient information from this document image and return a JSON object with: "
    "patient_id (optional), name, age, address, preferences (object with any relevant details). "
    "Return valid JSON only."
)


async def _extract_text_from_file(file: UploadFile) -> str:
    content_type = (file.content_type or "").split(";")[0].strip()
    data = await file.read()

    if content_type == "application/pdf" or file.filename.endswith(".pdf"):
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
        if not result.get("name") and not result.get("patient_id"):
            raise ValueError(repr(result))
        return f"__vision_result__:{__import__('json').dumps(result)}"

    if content_type.startswith("text/") or file.filename.endswith(".txt"):
        return data.decode("utf-8", errors="replace")

    raise TypeError(content_type or "unknown")


@router.post("/file")
async def ingest_file(
    file: UploadFile,
    context: Annotated[str | None, Form()] = None,
    patient_id: Annotated[str | None, Form()] = None,
):
    try:
        raw = await _extract_text_from_file(file)
    except ImportError:
        return JSONResponse(
            status_code=501,
            content=err("pdfplumber is not installed; PDF ingest unavailable"),
        )
    except TypeError as exc:
        return JSONResponse(
            status_code=415,
            content=err(f"Unsupported file type: {exc}"),
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))

    # Vision path already returns extracted dict — short-circuit extraction
    if raw.startswith("__vision_result__:"):
        import json as _json
        extracted = _json.loads(raw[len("__vision_result__:"):])
        if patient_id:
            extracted["patient_id"] = patient_id
    else:
        combined = f"{context}\n\n{raw}" if context else raw
        try:
            extracted = _extract_patient_from_text(combined, patient_id)
        except ValueError as exc:
            return JSONResponse(
                status_code=422,
                content={"success": False, "error": "extraction_failed", "raw": str(exc)},
            )
        except Exception as exc:
            return JSONResponse(status_code=500, content=err(str(exc)))

    try:
        pid = write_patient(extracted)
        detect_status = await _trigger_detect(pid, "patient_create")
        return ok({"patient_id": pid, "extracted": extracted, "detect_status": detect_status})
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))
