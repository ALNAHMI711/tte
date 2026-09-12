"""Emergency-stop state for the trading automation boundary."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class KillSwitchState:
    enabled: bool
    reason: str = ""


class KillSwitch:
    """Thread-safe stop gate that blocks new orders without liquidating positions."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._state = KillSwitchState(enabled=False)

    def activate(self, reason: str = "manual emergency stop") -> KillSwitchState:
        normalized = reason.strip() if isinstance(reason, str) else ""
        if not normalized:
            normalized = "manual emergency stop"
        with self._lock:
            self._state = KillSwitchState(enabled=True, reason=normalized)
            return self._state

    def deactivate(self) -> KillSwitchState:
        with self._lock:
            self._state = KillSwitchState(enabled=False)
            return self._state

    def snapshot(self) -> KillSwitchState:
        with self._lock:
            return self._state

    def blocks_new_orders(self) -> bool:
        return self.snapshot().enabled
