"""Composed live-readiness gate for Binance without enabling live orders."""
from __future__ import annotations

from dataclasses import dataclass

from .binance_connectivity import BinanceConnectivityResult
from .binance_preflight import BinancePreflightReport, run_binance_preflight


@dataclass(frozen=True)
class LiveGateInputs:
    """Inputs already verified by independent safety stages."""

    live_requested: bool
    api_key_configured: bool
    trading_permission: bool
    withdrawal_permission: bool
    trusted_ips_only: bool
    server_ip_configured: bool
    risk_configured: bool
    dry_run_passed: bool
    connectivity: BinanceConnectivityResult | None = None


def evaluate_live_gate(inputs: LiveGateInputs) -> BinancePreflightReport:
    """Fail closed unless every required safety stage, including Testnet connectivity, passes."""
    connectivity_passed = (
        inputs.connectivity is not None
        and inputs.connectivity.reachable
        and inputs.connectivity.environment == "testnet"
        and "orders=not_supported" in inputs.connectivity.checks
    )
    report = run_binance_preflight(
        live_requested=inputs.live_requested,
        api_key_configured=inputs.api_key_configured,
        trading_permission=inputs.trading_permission,
        withdrawal_permission=inputs.withdrawal_permission,
        trusted_ips_only=inputs.trusted_ips_only,
        server_ip_configured=inputs.server_ip_configured,
        risk_configured=inputs.risk_configured,
        dry_run_passed=inputs.dry_run_passed,
    )
    return BinancePreflightReport(
        checks=report.checks
        + (
            type(report.checks[0])(
                "testnet_connectivity",
                type(report.checks[0].status).PASS
                if connectivity_passed
                else type(report.checks[0].status).FAIL,
                "Binance Testnet connectivity verified"
                if connectivity_passed
                else "Binance Testnet connectivity is required",
            ),
        )
    )
