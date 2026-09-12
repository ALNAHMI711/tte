"""Small, dependency-free audit event model and bounded audit log store."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol


class AuditPersistence(Protocol):
    """Durable sink contract for audit events."""

    def append(self, event: "AuditEvent") -> int:
        """Persist an event and return its durable sequence number."""


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
    """Thread-safe bounded audit cache with an optional durable persistence sink.

    If a persistence sink is configured, it is written before the in-memory cache
    so a persistence failure never produces a locally successful audit record.
    Production callers should treat a persistence exception as an operational
    failure rather than silently falling back to memory-only logging.
    """

    def __init__(self, max_events: int = 1000, persistence: AuditPersistence | None = None) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be positive")
        self.max_events = max_events
        self.persistence = persistence
        self._lock = Lock()
        self._events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> AuditEvent:
        if not isinstance(event, AuditEvent):
            raise TypeError("event must be an AuditEvent")
        if self.persistence is not None:
            self.persistence.append(event)
        with self._lock:
            self._events.append(event)
            if len(self._events) > self.max_events:
                del self._events[: len(self._events) - self.max_events]
        return event

    def snapshot(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)
