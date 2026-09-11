"""Safe Binance Spot Testnet connectivity preflight.

This module performs read-only connectivity checks through the existing market
client. It does not authenticate, place orders, or enable live execution.
"""
from __future__ import annotations

from dataclasses import dataclass

from .binance_market import BinanceMarketClient, BinanceMarketError


@dataclass(frozen=True)
class BinanceConnectivityResult:
    reachable: bool
    environment: str
    checks: tuple[str, ...]


class BinanceConnectivityError(RuntimeError):
    """Raised when the Testnet connectivity preflight cannot complete safely."""


def run_connectivity_check(client: BinanceMarketClient | None = None) -> BinanceConnectivityResult:
    """Verify that the configured Binance Testnet public API is reachable."""
    market = client or BinanceMarketClient()
    try:
        market.ping()
    except BinanceMarketError as exc:
        raise BinanceConnectivityError("Binance Testnet connectivity check failed") from exc
    return BinanceConnectivityResult(
        reachable=True,
        environment=market.environment.value,
        checks=("environment=testnet", "public_api=reachable", "orders=not_supported"),
    )
