"""Read-only unified Binance readiness composition.

This module composes existing safety signals without enabling LIVE trading,
placing orders, or contacting Binance on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from .binance_connectivity import BinanceConnectivityResult
from .binance_preflight import BinancePreflightReport
from .live_gate import LiveGateInputs, evaluate_live_gate
from .server_ip import PublicIPResult


@dataclass(frozen=True)
class BinanceReadinessStatus:
    """Single immutable snapshot for dashboard/control-plane readiness."""

    preflight: BinancePreflightReport
    connectivity: BinanceConnectivityResult | None
    server_ip: PublicIPResult | None

    @property
    def ready(self) -> bool:
        """Return true only when every composed safety signal passes."""
        return (
            self.preflight.passed
            and self.connectivity is not None
            and self.connectivity.reachable
            and self.connectivity.environment == "testnet"
            and "orders=not_supported" in self.connectivity.checks
            and self.server_ip is not None
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize a dashboard-safe readiness snapshot without credentials."""
        return {
            "ready": self.ready,
            "live_enabled": False,
            "preflight": self.preflight.to_dict(),
            "connectivity": None
            if self.connectivity is None
            else {
                "reachable": self.connectivity.reachable,
                "environment": self.connectivity.environment,
                "checks": list(self.connectivity.checks),
            },
            "server_ip": None
            if self.server_ip is None
            else {"ip": self.server_ip.ip, "source": self.server_ip.source},
        }


def compose_binance_readiness(
    *,
    inputs: LiveGateInputs,
    server_ip: PublicIPResult | None = None,
) -> BinanceReadinessStatus:
    """Compose existing Binance safety stages into one read-only status object."""
    return BinanceReadinessStatus(
        preflight=evaluate_live_gate(inputs),
        connectivity=inputs.connectivity,
        server_ip=server_ip,
    )
