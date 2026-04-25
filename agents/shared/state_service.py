"""In-memory state for request routing during scaffold phase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping


@dataclass(frozen=True)
class PendingRequest:
    request_id: str
    query: str
    domain: str
    user_sender_address: str | None
    routed_address: str
    created_at: datetime


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
