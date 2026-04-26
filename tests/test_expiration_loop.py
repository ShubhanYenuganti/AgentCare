"""Tests for the executor expiration loop.

Tests:
11.1 - Running the loop twice for the same overdue action writes exactly one
       notification_log entry per channel (dashboard, asi_one).
11.2 - The expiration loop marks actions with review_by in the past and
       completed=0 as overdue.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

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


def _past_timestamp(hours: int = 2) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _future_timestamp(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def seed_overdue_action(**overrides) -> str:
    """Create a patient and action with review_by in the past and completed=0."""
    from agents.shared.db import write_action, write_patient
    patient_id = write_patient({"name": "Overdue Patient", "age": 75})
    data = {
        "patient_id": patient_id,
        "domain": "health",
        "type": "check",
        "description": "Overdue check",
        "urgency_level": "tier_2",
        "review_by": _past_timestamp(4),  # 4 hours past due
    }
    data.update(overrides)
    return write_action(data)


def _run_expiration_loop_iteration() -> int:
    """
    Simulate one expiration loop iteration using the same DB helpers that
    the executor's expiration_check uses. Returns count of actions processed.
    """
    from agents.shared.db import (
        get_overdue_actions,
        has_been_notified,
        log_expiration_notification,
        mark_action_overdue,
        write_notification,
    )
    overdue = get_overdue_actions()
    for action in overdue:
        action_id = action["action_id"]
        patient_id = action.get("patient_id", "")
        mark_action_overdue(action_id)
        for channel in ("dashboard", "asi_one"):
            if has_been_notified(action_id, channel):
                continue
            if channel == "dashboard":
                write_notification(
                    type="overdue",
                    action_id=action_id,
                    patient_id=patient_id,
                    title=f"Overdue: {action.get('type', 'task')} for {patient_id}",
                    body=action.get("description", ""),
                )
            log_expiration_notification(action_id, channel)
    return len(overdue)


def _count_expiration_notifications(action_id: str, channel: str) -> int:
    from agents.shared.db import get_connection
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM expiration_notifications WHERE action_id=? AND channel=?",
            (action_id, channel),
        ).fetchone()
    return row[0] if row else 0


# ── 11.1 Dedup tests ─────────────────────────────────────────────────────────

class TestExpirationLoopDedup:
    def test_dashboard_notification_deduped(self):
        """Running loop twice produces exactly one notification_log entry for dashboard."""
        action_id = seed_overdue_action()

        # Run loop twice
        _run_expiration_loop_iteration()
        _run_expiration_loop_iteration()

        count = _count_expiration_notifications(action_id, "dashboard")
        assert count == 1, f"Expected 1 dashboard notification, got {count}"

    def test_asi_one_notification_deduped(self):
        """Running loop twice produces exactly one notification_log entry for asi_one."""
        action_id = seed_overdue_action()

        _run_expiration_loop_iteration()
        _run_expiration_loop_iteration()

        count = _count_expiration_notifications(action_id, "asi_one")
        assert count == 1, f"Expected 1 asi_one notification, got {count}"

    def test_both_channels_exactly_one_each(self):
        """Running loop N times produces exactly 1 entry per channel, not N."""
        action_id = seed_overdue_action()

        for _ in range(5):
            _run_expiration_loop_iteration()

        dashboard_count = _count_expiration_notifications(action_id, "dashboard")
        asi_one_count = _count_expiration_notifications(action_id, "asi_one")
        assert dashboard_count == 1, f"dashboard: expected 1, got {dashboard_count}"
        assert asi_one_count == 1, f"asi_one: expected 1, got {asi_one_count}"

    def test_separate_actions_get_separate_notifications(self):
        """Two different overdue actions each get their own notification entries."""
        action_id_a = seed_overdue_action()
        action_id_b = seed_overdue_action()

        _run_expiration_loop_iteration()
        _run_expiration_loop_iteration()

        assert _count_expiration_notifications(action_id_a, "dashboard") == 1
        assert _count_expiration_notifications(action_id_b, "dashboard") == 1


# ── 11.2 Overdue marking tests ────────────────────────────────────────────────

class TestExpirationLoopOverdueMarking:
    def test_past_review_by_action_is_returned_as_overdue(self):
        """Action with review_by in the past and completed=0 is returned by get_overdue_actions."""
        from agents.shared.db import get_overdue_actions

        action_id = seed_overdue_action()
        overdue = get_overdue_actions()
        assert any(a["action_id"] == action_id for a in overdue)

    def test_mark_action_overdue_sets_is_overdue_flag(self):
        """mark_action_overdue sets is_overdue=1 in DB."""
        from agents.shared.db import get_action, mark_action_overdue

        action_id = seed_overdue_action()
        mark_action_overdue(action_id)
        action = get_action(action_id)
        assert action["is_overdue"] == 1

    def test_future_review_by_action_not_overdue(self):
        """Action with review_by in the future is NOT returned by get_overdue_actions."""
        from agents.shared.db import get_overdue_actions, write_action, write_patient

        patient_id = write_patient({"name": "Future Patient", "age": 60})
        future_action_id = write_action({
            "patient_id": patient_id,
            "domain": "health",
            "type": "check",
            "description": "Future check",
            "urgency_level": "tier_3",
            "review_by": _future_timestamp(48),
        })
        overdue = get_overdue_actions()
        assert not any(a["action_id"] == future_action_id for a in overdue)

    def test_completed_action_not_overdue(self):
        """Action with completed=1 is NOT returned as overdue even if past review_by."""
        from agents.shared.db import get_overdue_actions, update_action

        action_id = seed_overdue_action()
        update_action(action_id, {"completed": 1})
        overdue = get_overdue_actions()
        assert not any(a["action_id"] == action_id for a in overdue)

    def test_expiration_loop_marks_action_overdue_in_db(self):
        """Running one loop iteration marks the overdue action in DB."""
        from agents.shared.db import get_action

        action_id = seed_overdue_action()
        _run_expiration_loop_iteration()
        action = get_action(action_id)
        assert action["is_overdue"] == 1

    def test_expiration_loop_escalates_urgency(self):
        """mark_action_overdue sets urgency_level to tier_0 (highest priority)."""
        from agents.shared.db import get_action, mark_action_overdue

        action_id = seed_overdue_action()
        mark_action_overdue(action_id)
        action = get_action(action_id)
        assert action["urgency_level"] == "tier_0"
