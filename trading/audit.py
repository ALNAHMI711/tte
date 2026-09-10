"""Small, dependency-free audit event model for security-sensitive actions."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
