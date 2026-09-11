from __future__ import annotations

import json
from io import BytesIO
from urllib.error import URLError

import pytest

from trading.binance_market import (
    TESTNET_BASE_URL,
    BinanceEnvironmentError,
    BinanceMarketClient,
    BinanceNetworkError,
    BinanceResponseError,
)


class FakeResponse:
    def __init__(self, payload: object):
        self.raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.raw


def test_client_is_locked_to_testnet() -> None:
    client = BinanceMarketClient()
    assert client.environment.value == "testnet"
    assert client.base_url == TESTNET_BASE_URL

    with pytest.raises(BinanceEnvironmentError):
        BinanceMarketClient("https://api.binance.com")

    with pytest.raises(BinanceEnvironmentError):
        BinanceMarketClient("https://testnet.binance.vision.evil.example")


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError):
        BinanceMarketClient(timeout_seconds=0)
    with pytest.raises(ValueError):
        BinanceMarketClient(timeout_seconds=-1)


def test_network_failures_are_normalized(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr("trading.binance_market.urlopen", fail)
    with pytest.raises(BinanceNetworkError):
        BinanceMarketClient().ping()


def test_invalid_json_is_rejected(monkeypatch) -> None:
    class BadResponse(FakeResponse):
        def __init__(self):
            self.raw = b"not-json"

    monkeypatch.setattr("trading.binance_market.urlopen", lambda *args, **kwargs: BadResponse())
    with pytest.raises(BinanceResponseError):
        BinanceMarketClient().ping()


def test_ticker_is_normalized_and_symbol_is_uppercase(monkeypatch) -> None:
    captured = {}

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse({"bidPrice": "100.25", "askPrice": "100.50"})

    monkeypatch.setattr("trading.binance_market.urlopen", fake_open)
    assert BinanceMarketClient(timeout_seconds=3).ticker("btcusdt") == (100.25, 100.50)
    assert "symbol=BTCUSDT" in captured["url"]
    assert captured["timeout"] == 3


def test_malformed_ticker_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        "trading.binance_market.urlopen",
        lambda *args, **kwargs: FakeResponse({"bidPrice": "100"}),
    )
    with pytest.raises(BinanceResponseError):
        BinanceMarketClient().ticker("BTCUSDT")


def test_order_book_is_normalized_and_limit_is_bounded(monkeypatch) -> None:
    monkeypatch.setattr(
        "trading.binance_market.urlopen",
        lambda *args, **kwargs: FakeResponse(
            {"bids": [["100", "2"]], "asks": [["101", "3"]]}
        ),
    )
    snapshot = BinanceMarketClient().order_book("btcusdt", limit=5)
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.bids == ((100.0, 2.0),)
    assert snapshot.asks == ((101.0, 3.0),)

    with pytest.raises(ValueError):
        BinanceMarketClient().order_book("BTCUSDT", limit=0)
    with pytest.raises(ValueError):
        BinanceMarketClient().order_book("BTCUSDT", limit=1001)


def test_candles_are_normalized_to_utc(monkeypatch) -> None:
    monkeypatch.setattr(
        "trading.binance_market.urlopen",
        lambda *args, **kwargs: FakeResponse(
            [[1700000000000, "100", "105", "99", "104", "12", "extra"]]
        ),
    )
    candles = BinanceMarketClient().candles("btcusdt", "1m", limit=1)
    assert len(candles) == 1
    assert candles[0].symbol == "BTCUSDT"
    assert candles[0].timeframe == "1m"
    assert candles[0].timestamp.tzinfo is not None
    assert candles[0].close == 104.0


def test_malformed_candles_and_limits_are_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        "trading.binance_market.urlopen",
        lambda *args, **kwargs: FakeResponse([[1700000000000, "100"]]),
    )
    with pytest.raises(BinanceResponseError):
        BinanceMarketClient().candles("BTCUSDT", "1m")

    with pytest.raises(ValueError):
        BinanceMarketClient().candles("BTCUSDT", "1m", limit=0)
    with pytest.raises(ValueError):
        BinanceMarketClient().candles("BTCUSDT", "1m", limit=1001)


def test_client_does_not_accept_live_url_even_with_trailing_slash() -> None:
    with pytest.raises(BinanceEnvironmentError):
        BinanceMarketClient("https://api.binance.com/")
