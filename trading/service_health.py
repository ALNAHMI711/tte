"""Application-level readiness composition without exposing sensitive errors."""
from __future__ import annotations

from trading.execution import ExecutionEngine
from trading.health import HealthChecker


def build_health_checker(engine: ExecutionEngine) -> HealthChecker:
    """Build readiness checks for dependencies owned by the execution engine."""
    checker = HealthChecker()
    checker.register("paper-store", engine.paper.healthcheck)
    return checker
