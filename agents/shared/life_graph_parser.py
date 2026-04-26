"""Domain-specific filtering for patient life graph snapshots."""

from __future__ import annotations

from typing import Any

_TOP_LEVEL_ALLOWLIST: dict[str, set[str]] = {
    "health": {
        "patient",
        "assigned_caregivers",
        "caregiver_links",
        "caregivers",
        "patient_updates",
        "actions",
        "action_chat",
        "notifications",
        "expiration_notifications",
    },
    "appointment": {
        "patient",
        "assigned_caregivers",
        "caregiver_links",
        "caregivers",
        "caregiver_schedule",
        "patient_updates",
        "actions",
        "action_chat",
        "notifications",
        "expiration_notifications",
    },
    "grocery": {
        "patient",
        "assigned_caregivers",
        "caregiver_links",
        "caregivers",
        "patient_updates",
        "actions",
        "action_chat",
        "notifications",
        "expiration_notifications",
    },
    "financial": {
        "patient",
        "patient_updates",
        "actions",
        "action_chat",
        "notifications",
        "expiration_notifications",
    },
}


def _domain_match(value: Any, domain: str) -> bool:
    if value in (None, "", "unknown"):
        return False
    return str(value).strip().lower() == domain


def _notification_matches_domain(note: dict[str, Any], domain: str, action_ids: set[str]) -> bool:
    action_id = str(note.get("action_id") or "")
    if action_id and action_id in action_ids:
        return True
    note_type = str(note.get("type") or "").lower()
    return domain in note_type


def parse_life_graph_for_domain(
    full_snapshot: dict[str, Any], domain: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Filter a full patient life graph into the data relevant for one domain.

    Returns:
      (filtered_snapshot, parse_meta)
    """
    normalized_domain = (domain or "").strip().lower()
    allowlist = _TOP_LEVEL_ALLOWLIST.get(normalized_domain, {"patient"})

    safe_snapshot = full_snapshot if isinstance(full_snapshot, dict) else {}
    input_keys = set(safe_snapshot.keys())
    filtered: dict[str, Any] = {}

    # Keep allowlisted top-level sections first.
    for key in sorted(allowlist):
        if key in safe_snapshot:
            filtered[key] = safe_snapshot[key]

    # Domain-scope mutable collections.
    actions = [
        item
        for item in (safe_snapshot.get("actions") or [])
        if isinstance(item, dict) and _domain_match(item.get("domain"), normalized_domain)
    ]
    action_ids = {str(item.get("action_id")) for item in actions if item.get("action_id")}

    updates = [
        item
        for item in (safe_snapshot.get("patient_updates") or [])
        if isinstance(item, dict) and _domain_match(item.get("domain"), normalized_domain)
    ]
    action_chat = [
        item
        for item in (safe_snapshot.get("action_chat") or [])
        if isinstance(item, dict) and str(item.get("action_id") or "") in action_ids
    ]
    notifications = [
        item
        for item in (safe_snapshot.get("notifications") or [])
        if isinstance(item, dict) and _notification_matches_domain(item, normalized_domain, action_ids)
    ]
    expiration_notifications = [
        item
        for item in (safe_snapshot.get("expiration_notifications") or [])
        if isinstance(item, dict) and str(item.get("action_id") or "") in action_ids
    ]

    filtered["actions"] = actions
    filtered["patient_updates"] = updates
    filtered["action_chat"] = action_chat
    filtered["notifications"] = notifications
    filtered["expiration_notifications"] = expiration_notifications

    if normalized_domain != "appointment":
        filtered.pop("caregiver_schedule", None)

    filtered_keys = set(filtered.keys())
    dropped_keys = sorted(input_keys - filtered_keys)

    parse_meta: dict[str, Any] = {
        "domain": normalized_domain,
        "kept_top_level_keys": sorted(filtered_keys),
        "dropped_top_level_keys": dropped_keys,
        "input_key_count": len(input_keys),
        "filtered_action_count": len(actions),
        "filtered_update_count": len(updates),
        "filtered_chat_count": len(action_chat),
        "filtered_notification_count": len(notifications),
    }
    return filtered, parse_meta
