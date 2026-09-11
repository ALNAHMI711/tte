from __future__ import annotations

import pytest

from trading.binance_connectivity import (
    BinanceConnectivityError,
    BinanceConnectivityResult,
    run_connectivity_check,
)
from trading.binance_market import BinanceMarketClient, BinanceNetworkError


class HealthyClient:
    environment = type("Environment", (), {"value": "testnet"})()

    def ping(self) -> bool:
        return True


class FailingClient:
    environment = type("Environment", (), {"value": "testnet"})()

    def ping(self) -> bool:
        raise BinanceNetworkError("transport failure")


def test_connectivity_check_returns_safe_testnet_result() -> None:
    result = run_connectivity_check(HealthyClient())

    assert isinstance(result, BinanceConnectivityResult)
    assert result.reachable is True
    assert result.environment == "testnet"
    assert "orders=not_supported" in result.checks


def test_connectivity_check_normalizes_market_errors() -> None:
    with pytest.raises(BinanceConnectivityError, match="connectivity check failed"):
        run_connectivity_check(FailingClient())


def test_default_client_remains_testnet_only() -> None:
    client = BinanceMarketClient()

    assert client.environment.value == "testnet"
    assert client.base_url == "https://testnet.binance.vision"
