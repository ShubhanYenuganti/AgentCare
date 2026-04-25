"""Patients router — live SQLite-backed reads/writes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.shared.db import get_all_patients, get_patient, write_patient

router = APIRouter(prefix="/patients", tags=["patients"])


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


class PatientBody(BaseModel):
    patient_id: str | None = None
    name: str | None = None
    age: int | None = None
    address: str | None = None
    pharmacy_name: str | None = None
    pharmacy_email: str | None = None
    doctor_name: str | None = None
    doctor_email: str | None = None
    preferences: dict | None = None
    active: int | None = None


@router.get("")
async def list_patients():
    try:
        return ok(get_all_patients())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("/{patient_id}")
async def fetch_patient(patient_id: str):
    try:
        patient = get_patient(patient_id)
        if not patient:
            return JSONResponse(status_code=404, content=err(f"Patient {patient_id!r} not found"))
        return ok(patient)
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
