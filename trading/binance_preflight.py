"""Deterministic safety checks required before any Binance live trading enablement."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PreflightStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: PreflightStatus
    detail: str


@dataclass(frozen=True)
class BinancePreflightReport:
    checks: tuple[PreflightCheck, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.status is PreflightStatus.PASS for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": [
                {"name": check.name, "status": check.status.value, "detail": check.detail}
                for check in self.checks
            ],
        }


def _check(name: str, condition: bool, passed: str, failed: str) -> PreflightCheck:
    return PreflightCheck(name, PreflightStatus.PASS if condition else PreflightStatus.FAIL, passed if condition else failed)


def run_binance_preflight(
    *,
    live_requested: bool,
    api_key_configured: bool,
    trading_permission: bool,
    withdrawal_permission: bool,
    trusted_ips_only: bool,
    server_ip_configured: bool,
    risk_configured: bool,
    dry_run_passed: bool,
) -> BinancePreflightReport:
    """Evaluate launch gates without making network calls or placing orders.

    This function intentionally fails closed. A withdrawal-enabled key, missing
    trusted-IP restriction, missing server IP, incomplete risk configuration, or
    failed dry run prevents live enablement.
    """
    checks = (
        _check("live_requested", live_requested, "LIVE explicitly requested", "LIVE is not explicitly requested"),
        _check("api_key", api_key_configured, "API key is configured", "API key is missing"),
        _check("trading_permission", trading_permission, "Trading permission detected", "Trading permission is missing"),
        _check("withdrawal_disabled", not withdrawal_permission, "Withdrawal permission is disabled", "Withdrawal permission must be disabled"),
        _check("trusted_ips_only", trusted_ips_only, "Trusted IP restriction is enabled", "Trusted IP restriction is required"),
        _check("server_ip", server_ip_configured, "Server outbound IP is configured", "Server outbound IP is not configured"),
        _check("risk_config", risk_configured, "Risk configuration is ready", "Risk configuration is incomplete"),
        _check("dry_run", dry_run_passed, "Dry run passed", "Dry run has not passed"),
    )
    return BinancePreflightReport(checks)
