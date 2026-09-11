from __future__ import annotations

import json
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import pytest

from trading.binance_symbols import (
    BinanceSymbolClient,
    BinanceSymbolNetworkError,
    BinanceSymbolResponseError,
)
from trading.binance_market import TESTNET_BASE_URL


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def payload(**overrides: object) -> dict[str, object]:
    symbol = {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.01000000"},
            {"filterType": "LOT_SIZE", "minQty": "0.00001000", "stepSize": "0.00001000"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "10.00000000"},
        ],
    }
    symbol.update(overrides)
    return {"symbols": [symbol]}


def test_symbol_filters_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse(payload())

    monkeypatch.setattr("trading.binance_symbols.urlopen", fake_urlopen)
    info = BinanceSymbolClient().symbol_info("btcusdt")

    parsed = urlparse(captured["url"])
    assert f"{parsed.scheme}://{parsed.netloc}" == TESTNET_BASE_URL
    assert parsed.path == "/api/v3/exchangeInfo"
    assert parse_qs(parsed.query) == {"symbol": ["BTCUSDT"]}
    assert info.symbol == "BTCUSDT"
    assert info.base_asset == "BTC"
    assert info.quote_asset == "USDT"
    assert info.min_quantity == 0.00001
    assert info.quantity_step == 0.00001
    assert info.min_notional == 10.0


def test_client_is_testnet_only() -> None:
    with pytest.raises(BinanceSymbolResponseError.__mro__[1], match="only Binance Spot Testnet"):
        BinanceSymbolClient(base_url="https://api.binance.com")


def test_empty_symbol_is_rejected() -> None:
    with pytest.raises(ValueError, match="symbol is required"):
        BinanceSymbolClient().symbol_info(" ")


def test_network_error_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("trading.binance_symbols.urlopen", lambda request, timeout: (_ for _ in ()).throw(URLError("offline")))
    with pytest.raises(BinanceSymbolNetworkError, match="exchange-info request failed"):
        BinanceSymbolClient().symbol_info("BTCUSDT")


def test_malformed_json_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadResponse(FakeResponse):
        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr("trading.binance_symbols.urlopen", lambda request, timeout: BadResponse(None))
    with pytest.raises(BinanceSymbolResponseError, match="invalid JSON"):
        BinanceSymbolClient().symbol_info("BTCUSDT")


def test_missing_required_filters_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    data = payload()
    data["symbols"][0]["filters"] = []
    monkeypatch.setattr("trading.binance_symbols.urlopen", lambda request, timeout: FakeResponse(data))
    with pytest.raises(BinanceSymbolResponseError, match="required symbol filters"):
        BinanceSymbolClient().symbol_info("BTCUSDT")


def test_non_trading_symbol_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("trading.binance_symbols.urlopen", lambda request, timeout: FakeResponse(payload(status="BREAK")))
    with pytest.raises(BinanceSymbolResponseError, match="not trading"):
        BinanceSymbolClient().symbol_info("BTCUSDT")


def test_invalid_quantity_filters_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    data = payload()
    data["symbols"][0]["filters"][1]["stepSize"] = "0"
    monkeypatch.setattr("trading.binance_symbols.urlopen", lambda request, timeout: FakeResponse(data))
    with pytest.raises(BinanceSymbolResponseError, match="quantity filters"):
        BinanceSymbolClient().symbol_info("BTCUSDT")


@pytest.mark.parametrize(
    ("filter_index", "field", "value"),
    [
        (1, "minQty", "-1"),
        (1, "stepSize", "NaN"),
        (2, "minNotional", "-1"),
    ],
)
def test_non_finite_or_negative_numeric_filters_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    filter_index: int,
    field: str,
    value: str,
) -> None:
    data = payload()
    data["symbols"][0]["filters"][filter_index][field] = value
    monkeypatch.setattr("trading.binance_symbols.urlopen", lambda request, timeout: FakeResponse(data))

    with pytest.raises(BinanceSymbolResponseError, match=rf"invalid {field}"):
        BinanceSymbolClient().symbol_info("BTCUSDT")


def test_unknown_symbol_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("trading.binance_symbols.urlopen", lambda request, timeout: FakeResponse({"symbols": []}))
    with pytest.raises(BinanceSymbolResponseError, match="missing or ambiguous"):
        BinanceSymbolClient().symbol_info("BTCUSDT")
