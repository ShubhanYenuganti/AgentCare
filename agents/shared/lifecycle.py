"""Deterministic action lifecycle transition validation (Sprint 2)."""

from __future__ import annotations

from typing import NamedTuple


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, action_id: str, from_state: str, to_state: str, reason: str) -> None:
        self.action_id = action_id
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            f"Invalid transition for action {action_id}: {from_state} -> {to_state}: {reason}"
        )


class TransitionResult(NamedTuple):
    valid: bool
    error: str | None


# Allowed state transitions: from_state -> set of allowed to_states
# States:
#   draft          - initial state, not yet reviewed
#   modification_in_progress - draft is being modified (locked)
#   reviewed       - caregiver reviewed, not yet completed
#   completed      - final state, action executed
#   overdue        - review_by deadline passed
#   escalated      - escalated beyond normal caregiver tier

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"modification_in_progress", "reviewed", "overdue", "completed"},
    "modification_in_progress": {"draft", "overdue"},  # returns to draft after mod
    "reviewed": {"completed", "overdue"},
    "overdue": {"escalated", "completed"},
    "escalated": {"completed"},
    "completed": set(),  # terminal
}


def _current_state(action: dict) -> str:
    """Derive logical state string from action record fields."""
    if action.get("completed"):
        return "completed"
    if action.get("is_overdue") and action.get("escalation_count", 0) > 1:
        return "escalated"
    if action.get("is_overdue"):
        return "overdue"
    if action.get("modification_in_progress"):
        return "modification_in_progress"
    if action.get("reviewed"):
        return "reviewed"
    return "draft"


def validate_transition(action: dict, to_state: str) -> TransitionResult:
    """
    Validate that transitioning the action to ``to_state`` is permitted.

    Returns a ``TransitionResult``. Does NOT mutate the action.
    """
    from_state = _current_state(action)
    allowed = _ALLOWED_TRANSITIONS.get(from_state, set())
    if to_state in allowed:
        return TransitionResult(valid=True, error=None)
    if from_state == to_state:
        return TransitionResult(valid=False, error=f"Action already in state '{from_state}'")
    return TransitionResult(
        valid=False,
        error=(
            f"Transition '{from_state}' -> '{to_state}' is not permitted. "
            f"Allowed: {sorted(allowed) or 'none (terminal state)'}"
        ),
    )


def require_transition(action: dict, to_state: str) -> None:
    """Like ``validate_transition`` but raises ``TransitionError`` on failure."""
    result = validate_transition(action, to_state)
    if not result.valid:
        raise TransitionError(
            action_id=action.get("action_id", "unknown"),
            from_state=_current_state(action),
            to_state=to_state,
            reason=result.error or "unknown reason",
        )


def current_state(action: dict) -> str:
    """Public accessor for the derived state string."""
    return _current_state(action)
