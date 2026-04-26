"""Tests asserting stable response envelope shapes for mock API endpoints
used by detection and approval flows."""

from __future__ import annotations

import os
import tempfile

# Point to a temp DB before any app imports so _db_path() resolves correctly.
_tmp = tempfile.mktemp(suffix=".db")
os.environ["SQLITE_DB_PATH"] = _tmp

from fastapi.testclient import TestClient  # noqa: E402

from agents.shared.db import init_db  # noqa: E402
from api.main import app  # noqa: E402

init_db()

client = TestClient(app)


def test_cvs_available():
    resp = client.get("/mock/cvs/available?doctor_name=Test+Doctor")
    assert resp.status_code == 200
    data = resp.json()
    assert "available_medications" in data


def test_cvs_refill():
    resp = client.post(
        "/mock/cvs/refill",
        json={"medication": "Lisinopril 10mg", "patient_id": "p1", "pharmacy": "CVS Mission St"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "confirmation_id" in data
    assert "estimated_ready" in data


def test_cal_available():
    resp = client.get("/mock/cal/available?doctor_name=Test+Doctor")
    assert resp.status_code == 200
    data = resp.json()
    assert "slots" in data


def test_cal_book():
    resp = client.post(
        "/mock/cal/book",
        json={"provider": "Dr. Anita Patel", "patient_id": "p1", "preferred_times": ["morning"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "confirmation_id" in data
    assert "appointment_datetime" in data


def test_instacart_cart():
    resp = client.post(
        "/mock/instacart/cart",
        json={"patient_id": "p1", "items": ["apples", "bananas"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "cart_id" in data
    assert "estimated_delivery" in data


def test_amazon_order():
    resp = client.post(
        "/mock/amazon/order",
        json={"patient_id": "p1", "items": ["vitamin C", "ibuprofen"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "order_id" in data
    assert "status" in data
    assert "estimated_delivery" in data


def test_grocery_order_alias():
    resp = client.post(
        "/mock/grocery/order",
        json={"patient_id": "p1", "items": ["milk", "eggs"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "order_id" in data
    assert "status" in data
    assert "estimated_delivery" in data


def test_caregivers_available():
    resp = client.post(
        "/mock/caregivers/available",
        json={
            "date": "2026-04-28",
            "manual_action_type": "companionship",
            "patient_id": "p1",
            "duration_hours": 2.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "available_caregivers" in data
    assert isinstance(data["available_caregivers"], list)
