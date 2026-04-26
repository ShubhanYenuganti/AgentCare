"""In-memory state for request routing and multi-domain fan-out correlation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class PendingRequest:
    request_id: str
    query: str
    domain: str
    intent: str  # "question" | "modification" | "scheduling" | "detection" | "mock"
    user_sender_address: str | None
    routed_address: str
    created_at: datetime
    action_id: str | None = None  # set when request originates from POST /actions/{id}/chat


class InMemoryRequestState:
    def __init__(self) -> None:
        self._store: dict[str, PendingRequest] = {}

    def set_request(self, pending: PendingRequest) -> None:
        self._store[pending.request_id] = pending

    def get_request(self, request_id: str) -> PendingRequest | None:
        return self._store.get(request_id)

    def all_requests(self) -> Mapping[str, PendingRequest]:
        return self._store.copy()

    def remove_request(self, request_id: str) -> PendingRequest | None:
        return self._store.pop(request_id, None)

    def remove_stale_requests(self, timeout_seconds: float) -> list[PendingRequest]:
        now = datetime.now(tz=timezone.utc)
        stale_ids = [
            request_id
            for request_id, pending in self._store.items()
            if (now - pending.created_at).total_seconds() >= timeout_seconds
        ]
        stale_requests: list[PendingRequest] = []
        for request_id in stale_ids:
            removed = self._store.pop(request_id, None)
            if removed is not None:
                stale_requests.append(removed)
        return stale_requests


request_state = InMemoryRequestState()


# ---------------------------------------------------------------------------
# Detection fan-out correlation (Sprint 2)
# ---------------------------------------------------------------------------

@dataclass
class PendingFanOut:
    """Tracks an in-flight detection fan-out across multiple domain supervisors."""

    pass_id: str
    patient_id: str
    user_sender_address: str | None
    target_domains: list[str]
    original_query: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    # domain -> result dict (None means still pending)
    domain_results: dict[str, Any | None] = field(default_factory=dict)
    # domain -> True if timed out
    domain_timeouts: dict[str, bool] = field(default_factory=dict)

    def record_result(self, domain: str, result: Any) -> None:
        self.domain_results[domain] = result

    def record_timeout(self, domain: str) -> None:
        self.domain_results[domain] = None
        self.domain_timeouts[domain] = True

    def is_complete(self) -> bool:
        return len(self.domain_results) >= len(self.target_domains)

    def pending_domains(self) -> list[str]:
        return [d for d in self.target_domains if d not in self.domain_results]

    def age_seconds(self) -> float:
        return (datetime.now(tz=timezone.utc) - self.created_at).total_seconds()


class FanOutRequestState:
    """Registry for active detection fan-outs keyed by pass_id."""

    def __init__(self) -> None:
        self._store: dict[str, PendingFanOut] = {}

    def register(self, fan_out: PendingFanOut) -> None:
        self._store[fan_out.pass_id] = fan_out

    def get(self, pass_id: str) -> PendingFanOut | None:
        return self._store.get(pass_id)

    def remove(self, pass_id: str) -> PendingFanOut | None:
        return self._store.pop(pass_id, None)

    def remove_stale(self, timeout_seconds: float) -> list[PendingFanOut]:
        now = datetime.now(tz=timezone.utc)
        stale_ids = [
            pid
            for pid, fan_out in self._store.items()
            if (now - fan_out.created_at).total_seconds() >= timeout_seconds
        ]
        stale = []
        for pid in stale_ids:
            removed = self._store.pop(pid, None)
            if removed is not None:
                stale.append(removed)
        return stale


fan_out_state = FanOutRequestState()
