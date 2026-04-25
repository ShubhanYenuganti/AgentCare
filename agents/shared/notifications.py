"""Notification delivery layer — Resend email with graceful degradation.

RESEND_API_KEY must be set in .env for live email delivery.
When absent, notifications are recorded in the DB but not sent externally.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_SUBJECT_MAP = {
    ("health", "pharmacy"): "Medication Refill Request — {patient}",
    ("health", "prescriber"): "URGENT: Clinical Escalation — {patient}",
    ("health", "provider"): "Health Care Action — {patient}",
    ("appointment", "clinic"): "Appointment Scheduling Request — {patient}",
    ("appointment", "caregiver"): "Care Visit Coordination — {patient}",
    ("grocery", "patient"): "Household Delivery Update — {patient}",
    ("grocery", "caregiver"): "Grocery Care Action — {patient}",
    ("financial", "caregiver"): "Financial Care Follow-up — {patient}",
}


def _resend_api_key() -> str | None:
    return os.getenv("RESEND_API_KEY") or None


def _resend_client():
    """Return an authenticated resend client, or None if key is absent."""
    key = _resend_api_key()
    if not key:
        return None
    try:
        import resend  # type: ignore

        resend.api_key = key
        return resend
    except ImportError:
        logger.warning(
            "resend package not installed. Email delivery disabled. "
            "Install with: pip install resend"
        )
        return None


def build_action_subject(action: dict[str, Any], patient_name: str | None = None) -> str:
    """Build a recipient-aware subject for action notifications."""
    domain = str(action.get("domain") or "").strip().lower()
    recipient_type = str(action.get("recipient_type") or "").strip().lower()
    template = _SUBJECT_MAP.get((domain, recipient_type), "Care Action — {patient}")
    patient = patient_name or action.get("patient_name") or action.get("patient_id") or "Patient"
    return template.format(patient=patient)


def send_email(
    to: str | list[str],
    subject: str,
    html_body: str,
    from_addr: str = "MACOS <noreply@notifications.macos-care.ai>",
) -> dict[str, Any]:
    """
    Send an email via Resend.

    Returns a result dict with ``sent=True/False`` and optional ``id`` or ``error``.
    """
    client = _resend_client()
    if client is None:
        logger.warning(
            "RESEND_API_KEY not configured. Email NOT sent to=%s subject=%r",
            to,
            subject,
        )
        return {"sent": False, "error": "RESEND_API_KEY not configured"}

    try:
        params = {
            "from": from_addr,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html_body,
        }
        result = client.Emails.send(params)
        logger.info("Email sent id=%s to=%s subject=%r", result.get("id"), to, subject)
        return {"sent": True, "id": result.get("id")}
    except Exception as exc:
        logger.error("Email send failed to=%s: %s", to, exc)
        return {"sent": False, "error": str(exc)}


def send_action_notification(
    action_id: str,
    patient_id: str,
    recipient_email: str,
    subject: str,
    body_html: str,
) -> dict[str, Any]:
    """
    High-level helper: send a notification for an action and record it in the DB.
    """
    from agents.shared.db import write_notification

    result = send_email(to=recipient_email, subject=subject, html_body=body_html)
    write_notification(
        type="action_email",
        action_id=action_id,
        patient_id=patient_id,
        title=subject,
        body=body_html[:500],
    )
    return result


def resend_configured() -> bool:
    """Return True if RESEND_API_KEY is present and the resend package is installed."""
    return _resend_client() is not None
