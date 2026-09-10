"""Framework-neutral liveness/readiness checks for safe service monitoring."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class HealthReport:
    status: str
    checks: tuple[CheckResult, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checks": [
                {"name": check.name, "ok": check.ok, "detail": check.detail}
                for check in self.checks
            ],
        }


class HealthChecker:
    """Separate process liveness from dependency readiness."""

    def __init__(self) -> None:
        self._checks: dict[str, Callable[[], object]] = {}

    def register(self, name: str, check: Callable[[], object]) -> None:
        if not name or not callable(check):
            raise ValueError("a check name and callable are required")
        self._checks[name] = check

    def liveness(self) -> HealthReport:
        return HealthReport(status="ok")

    def readiness(self) -> HealthReport:
        results: list[CheckResult] = []
        for name, check in self._checks.items():
            try:
                result = check()
                if isinstance(result, CheckResult):
                    results.append(result)
                elif result is True:
                    results.append(CheckResult(name, True))
                elif result is False:
                    results.append(CheckResult(name, False, "check returned false"))
                else:
                    results.append(CheckResult(name, True, "ok"))
            except Exception:
                # Do not expose exception text: it may contain credentials or internals.
                results.append(CheckResult(name, False, "check failed"))
        status = "ok" if all(item.ok for item in results) else "not_ready"
        return HealthReport(status=status, checks=tuple(results))
