"""Mock API routes for external dependencies used by worker/action execution."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import random

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agents.shared.db import get_connection

router = APIRouter(prefix="/mock", tags=["mock"])


def _confirmation(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{random.randint(0, 999999):06d}"


def _next_business_day(start: date | None = None, offset: int = 1) -> date:
    current = (start or datetime.now(timezone.utc).date())
    found = 0
    while found < offset:
        current = current + timedelta(days=1)
        if current.weekday() < 5:
            found += 1
    return current


def _fmt_slot_label(date_value: date, start_time: str, end_time: str) -> str:
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    day_label = date_value.strftime("%a %b") + f" {date_value.day}"
    return f"{day_label} · {start.strftime('%-I:%M%p').lower()}–{end.strftime('%-I:%M%p').lower()}"


class CVSRefillRequest(BaseModel):
    medication: str
    patient_id: str
    pharmacy: str


class CalBookRequest(BaseModel):
    provider: str
    patient_id: str
    preferred_times: list[str]


class InstacartCartRequest(BaseModel):
    patient_id: str
    items: list[str]
    dietary_flags: list[str] | None = None


class AmazonOrderRequest(BaseModel):
    patient_id: str
    items: list[str]
    dietary_flags: list[str] | None = None


class CaregiverAvailabilityRequest(BaseModel):
    date: str
    manual_action_type: str
    patient_id: str
    duration_hours: float = Field(ge=0.5, le=12)


_AVAILABLE_MEDICATIONS = [
    {"name": "Lisinopril 10mg", "form": "tablet", "stock_status": "in_stock", "pharmacy": "CVS Mission St"},
    {"name": "Metformin 500mg", "form": "tablet", "stock_status": "in_stock", "pharmacy": "CVS Mission St"},
    {"name": "Atorvastatin 20mg", "form": "tablet", "stock_status": "low_stock", "pharmacy": "CVS Mission St"},
    {"name": "Levothyroxine 75mcg", "form": "tablet", "stock_status": "in_stock", "pharmacy": "CVS Mission St"},
]

_CAL_PROVIDERS = ["Dr. Anita Patel", "Dr. Ravi Singh", "NP Monica Tran"]


@router.get("/cvs/available")
async def cvs_available(
    doctor_name: str = Query(..., min_length=2),
    medication: str | None = Query(default=None),
):
    rows = _AVAILABLE_MEDICATIONS
    if medication:
        needle = medication.strip().lower()
        rows = [item for item in rows if needle in item["name"].lower()]
    return {
        "doctor_name": doctor_name,
        "available_medications": rows,
        "total_available": len(rows),
    }


@router.post("/cvs/refill")
async def cvs_refill(body: CVSRefillRequest):
    if not body.medication.strip():
        raise HTTPException(status_code=400, detail="medication is required")

    ready_dt = datetime.combine(
        _next_business_day(offset=1),
        datetime.strptime("14:00", "%H:%M").time(),
        tzinfo=timezone.utc,
    )
    return {
        "status": "accepted",
        "confirmation_id": _confirmation("CVS"),
        "estimated_ready": ready_dt.isoformat().replace("+00:00", "Z"),
        "pharmacy_phone": "+1-555-0288",
        "pharmacist_name": "David Nguyen",
        "notes": "Refill authorized.",
    }


@router.get("/cal/available")
async def cal_available(
    doctor_name: str = Query(..., min_length=2),
    provider: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
):
    providers = [provider] if provider else _CAL_PROVIDERS
    base_day = _next_business_day(offset=1)

    slots = []
    for i, provider_name in enumerate(providers):
        day = _next_business_day(start=base_day - timedelta(days=1), offset=i + 1)
        slots.append(
            {
                "doctor_name": doctor_name,
                "provider": provider_name,
                "patient_id": patient_id,
                "available_times": [
                    datetime.combine(day, datetime.strptime("09:00", "%H:%M").time(), tzinfo=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    datetime.combine(day, datetime.strptime("13:30", "%H:%M").time(), tzinfo=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                ],
            }
        )

    return {"doctor_name": doctor_name, "slots": slots, "total_providers": len(slots)}


@router.post("/cal/book")
async def cal_book(body: CalBookRequest):
    booking_day = _next_business_day(offset=1)
    hour = 10
    if any("afternoon" in item.lower() for item in body.preferred_times):
        hour = 14
    elif any("evening" in item.lower() for item in body.preferred_times):
        hour = 17

    appt_dt = datetime.combine(
        booking_day,
        datetime.strptime(f"{hour:02d}:00", "%H:%M").time(),
        tzinfo=timezone.utc,
    )
    return {
        "status": "booked",
        "confirmation_id": _confirmation("CAL"),
        "appointment_datetime": appt_dt.isoformat().replace("+00:00", "Z"),
        "location": "400 Parnassus Ave, SF CA 94143",
        "provider_confirmation_sent": True,
        "notes": "Preferred slot confirmed. Bring current medication list.",
    }


@router.post("/instacart/cart")
async def instacart_cart(body: InstacartCartRequest):
    delivery_dt = datetime.combine(
        _next_business_day(offset=1),
        datetime.strptime("11:00", "%H:%M").time(),
        tzinfo=timezone.utc,
    )
    return {
        "status": "cart_created",
        "cart_id": _confirmation("INST"),
        "estimated_delivery": delivery_dt.isoformat().replace("+00:00", "Z"),
        "total_estimate": round(max(12.5, len(body.items) * 8.2), 2),
        "items_confirmed": [f"{item} x1" for item in body.items],
        "dietary_verified": True,
        "store": "Safeway Mission St",
    }


@router.post("/amazon/order")
async def amazon_order(body: AmazonOrderRequest):
    delivery_dt = datetime.combine(
        _next_business_day(offset=2),
        datetime.strptime("18:00", "%H:%M").time(),
        tzinfo=timezone.utc,
    )
    order_id = _confirmation("AMZ")
    return {
        "status": "cart_created",
        "order_id": order_id,
        "cart_id": order_id,
        "estimated_delivery": delivery_dt.isoformat().replace("+00:00", "Z"),
        "total_estimate": round(max(9.99, len(body.items) * 7.5), 2),
        "items_confirmed": [f"{item} x1" for item in body.items],
        "dietary_verified": True,
        "store": "Amazon",
    }


@router.post("/amazon/reorder")
async def amazon_reorder_alias(body: AmazonOrderRequest):
    return await amazon_order(body)


@router.post("/grocery/order")
async def grocery_order_alias(body: AmazonOrderRequest):
    return await amazon_order(body)


def _available_caregivers_for_date(date_checked: str, patient_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cs.caregiver_id,
                   c.name,
                   c.email,
                   cs.date,
                   cs.start_time,
                   cs.end_time,
                   CASE WHEN pc.patient_id IS NULL THEN 0 ELSE 1 END AS assigned_to_patient
            FROM caregiver_schedule cs
            JOIN caregivers c ON c.caregiver_id = cs.caregiver_id
            LEFT JOIN patient_caregivers pc
              ON pc.caregiver_id = cs.caregiver_id
             AND pc.patient_id = ?
            WHERE cs.date = ?
              AND cs.available = 1
              AND cs.booked = 0
            ORDER BY assigned_to_patient DESC, cs.start_time ASC
            """,
            (patient_id, date_checked),
        ).fetchall()

    parsed: list[dict] = []
    for row in rows:
        row_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        parsed.append(
            {
                "caregiver_id": row["caregiver_id"],
                "name": row["name"],
                "email": row["email"],
                "date": row["date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "assigned_to_patient": bool(row["assigned_to_patient"]),
                "slot_label": _fmt_slot_label(row_date, row["start_time"], row["end_time"]),
            }
        )
    return parsed


@router.post("/caregivers/available")
async def caregivers_available(body: CaregiverAvailabilityRequest):
    try:
        requested = datetime.strptime(body.date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc

    candidate_dates = [requested]
    next_day = requested
    while len(candidate_dates) < 4:
        next_day = _next_business_day(start=next_day, offset=1)
        candidate_dates.append(next_day)

    matched_rows: list[dict] = []
    matched_date = requested
    for candidate in candidate_dates:
        date_str = candidate.isoformat()
        matched_rows = _available_caregivers_for_date(date_str, body.patient_id)
        if matched_rows:
            matched_date = candidate
            break

    return {
        "available_caregivers": matched_rows,
        "date_checked": matched_date.isoformat(),
        "total_available": len(matched_rows),
    }
