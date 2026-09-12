"""Small, dependency-free audit event model and bounded audit log store."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit record; secrets and credentials must never be placed in details."""

    action: str
    actor: str
    outcome: str
    timestamp: str
    request_id: str = ""
    details: tuple[tuple[str, str], ...] = ()

    @classmethod
    def create(
        cls,
        action: str,
        actor: str,
        outcome: str,
        *,
        request_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> "AuditEvent":
        safe_details = tuple(sorted((str(k), str(v)) for k, v in (details or {}).items()))
        return cls(
            action=action,
            actor=actor,
            outcome=outcome,
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=request_id,
            details=safe_details,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditLog:
    """Thread-safe bounded event store for the control-plane foundation.

    The store intentionally keeps only security metadata. Production deployments
    should replace it with durable, access-controlled storage without changing the
    ``record``/``snapshot`` contract.
    """

    def __init__(self, max_events: int = 1000) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be positive")
        self.max_events = max_events
        self._lock = Lock()
        self._events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> AuditEvent:
        if not isinstance(event, AuditEvent):
            raise TypeError("event must be an AuditEvent")
        with self._lock:
            self._events.append(event)
            if len(self._events) > self.max_events:
                del self._events[: len(self._events) - self.max_events]
        return event

    def snapshot(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)
