"""Integration tests for POST /internal/detect fan-out behaviour.

The executor's internal_detect endpoint is a uagents endpoint, not a FastAPI
route. We test the fan-out logic by calling _detection_domains_for_trigger
and the DB-level helpers that the executor relies on.
"""

from __future__ import annotations

import os
import tempfile

import pytest

_tmp = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SQLITE_DB_PATH", _tmp)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["SQLITE_DB_PATH"] = db_path
    from agents.shared.db import init_db
    init_db()
    yield
    os.environ["SQLITE_DB_PATH"] = _tmp


# ── 7.3 Fan-out logic tests ───────────────────────────────────────────────────

class TestExecutorDetectFanOut:
    def test_patient_create_fans_out_to_all_domains(self):
        """patient_create trigger returns all 4 domain targets."""
        from agents.executor.agent import _detection_domains_for_trigger

        domains = _detection_domains_for_trigger("patient_create", updated_fields=None)
        assert set(domains) == {"health", "appointment", "grocery", "financial"}, domains

    def test_patient_update_health_fans_out_to_health_only(self):
        """patient_update with domain_hint=health fans out to health only."""
        from agents.executor.agent import _detection_domains_for_trigger

        domains = _detection_domains_for_trigger("patient_update", updated_fields=None, domain_hint="health")
        assert domains == ["health"], domains

    def test_patient_update_no_domain_fans_out_to_all(self):
        """patient_update without domain hint fans out to all domains."""
        from agents.executor.agent import _detection_domains_for_trigger

        domains = _detection_domains_for_trigger("patient_update", updated_fields=None)
        assert set(domains) == {"health", "appointment", "grocery", "financial"}, domains

    def test_patient_update_grocery_fans_out_to_grocery_only(self):
        """patient_update with domain_hint=grocery fans out to grocery only."""
        from agents.executor.agent import _detection_domains_for_trigger

        domains = _detection_domains_for_trigger("patient_update", updated_fields=None, domain_hint="grocery")
        assert domains == ["grocery"], domains

    def test_patient_update_appointment_fans_out_to_appointment_only(self):
        from agents.executor.agent import _detection_domains_for_trigger

        domains = _detection_domains_for_trigger("patient_update", updated_fields=None, domain_hint="appointment")
        assert domains == ["appointment"], domains

    def test_patient_update_financial_fans_out_to_financial_only(self):
        from agents.executor.agent import _detection_domains_for_trigger

        domains = _detection_domains_for_trigger("patient_update", updated_fields=None, domain_hint="financial")
        assert domains == ["financial"], domains
