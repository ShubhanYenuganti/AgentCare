"""Supervisor utility helpers."""

from __future__ import annotations

from agents.shared.llm import call_claude_json


def _risk_score_drafts(
    drafts: list[dict],
    patient_snapshot: dict,
    org_context: dict,
) -> list[dict]:
    system = (
        "You are a care-operations risk assessor. "
        "Given a list of action drafts and patient context, return a JSON array with the same "
        "drafts but with potentially upgraded urgency_level (tier_0 > tier_1 > tier_2 > tier_3) "
        "and adjusted review_by (ISO datetime string). "
        "Only change urgency_level and review_by fields. Return the full array."
    )
    user = (
        f"Patient snapshot: {patient_snapshot}\n"
        f"Org context: {org_context}\n"
        f"Drafts: {drafts}\n\n"
        "Return a JSON array of the same drafts with updated urgency_level and review_by only."
    )
    result = call_claude_json(system, user, max_tokens=600)
    if isinstance(result, list) and len(result) == len(drafts):
        return result
    return drafts
