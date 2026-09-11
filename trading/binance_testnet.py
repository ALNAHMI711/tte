"""Binance Testnet preflight boundary; no live trading is implemented here."""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address


class TestnetPreflightError(ValueError):
    """Raised when a Binance Testnet configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class BinanceTestnetConfig:
    api_key: str
    api_secret: str
    trusted_ip: str
    withdrawal_enabled: bool = False
    testnet: bool = True

    def validate(self) -> None:
        if not self.testnet:
            raise TestnetPreflightError("only Binance Testnet is permitted by this boundary")
        if not self.api_key or not self.api_secret:
            raise TestnetPreflightError("Binance Testnet credentials are required")
        try:
            ip_address(self.trusted_ip)
        except ValueError as exc:
            raise TestnetPreflightError("trusted outbound IP must be valid") from exc
        if self.withdrawal_enabled:
            raise TestnetPreflightError("withdrawal permission must be disabled")


def run_preflight(config: BinanceTestnetConfig) -> tuple[str, ...]:
    """Validate safety prerequisites without contacting Binance or placing orders."""
    config.validate()
    return (
        "environment=testnet",
        "withdrawals=disabled",
        "trusted_ip=valid",
        "credentials=present",
        "live_execution=blocked",
    )
