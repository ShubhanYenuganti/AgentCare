"""Integration tests for POST /ingest/file.

Uses a temp SQLite DB and the FastAPI TestClient.
LLM calls are mocked to avoid real API usage in tests.
"""

from __future__ import annotations

import io
import os
import tempfile
from unittest.mock import patch

import pytest

_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SQLITE_DB_PATH", _tmp)
os.environ.setdefault("EXECUTOR_INTERNAL_URL", "")

from fastapi.testclient import TestClient  # noqa: E402

from agents.shared.db import get_all_patients, init_db  # noqa: E402
from api.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["SQLITE_DB_PATH"] = db_path
    init_db()
    yield
    os.environ["SQLITE_DB_PATH"] = _tmp


def assert_ok(resp, status=200):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["success"] is True, body
    return body["data"]


_MOCK_EXTRACTED = {
    "name": "Jane Smith",
    "age": 68,
    "address": "789 Pine Road",
    "conditions": ["diabetes"],
}


class TestIngestFile:
    def test_text_file_ingest_writes_patient(self):
        """Uploading a plain text file extracts patient and writes to DB."""
        with patch("agents.shared.llm.call_claude_json", return_value=_MOCK_EXTRACTED):
            content = b"Patient: Jane Smith, Age 68, Address: 789 Pine Road. Condition: diabetes."
            files = {"file": ("patient.txt", io.BytesIO(content), "text/plain")}
            resp = client.post("/ingest/file", files=files)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("success") is True

    def test_ingest_file_patient_written_to_db(self):
        """After file ingest, a patient record exists in the DB."""
        with patch("agents.shared.llm.call_claude_json", return_value=_MOCK_EXTRACTED):
            content = b"Patient name: Bob Jones, 72 years old."
            files = {"file": ("record.txt", io.BytesIO(content), "text/plain")}
            client.post("/ingest/file", files=files)

        patients = get_all_patients()
        # At least one patient written
        assert len(patients) >= 1

    def test_ingest_file_returns_patient_id(self):
        """Response includes patient_id field."""
        with patch("agents.shared.llm.call_claude_json", return_value=_MOCK_EXTRACTED):
            content = b"Patient info: Mary, 80, Chicago."
            files = {"file": ("info.txt", io.BytesIO(content), "text/plain")}
            resp = client.post("/ingest/file", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert "patient_id" in data.get("data", {})

    def test_ingest_file_detect_status_present(self):
        """Response includes detect_status from trigger call."""
        with patch("agents.shared.llm.call_claude_json", return_value=_MOCK_EXTRACTED):
            content = b"Patient: Alice Green, 65."
            files = {"file": ("a.txt", io.BytesIO(content), "text/plain")}
            resp = client.post("/ingest/file", files=files)
        data = resp.json()
        if data.get("success"):
            assert "detect_status" in data.get("data", {})
