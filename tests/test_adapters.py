import pytest

from trading.adapters import (
    AccountSnapshot,
    AdapterCapabilities,
    LiveTradingBlocked,
    SafeAdapter,
    SymbolInfo,
    TradingEnvironment,
    WithdrawalPermissionError,
    enforce_environment,
    enforce_safe_account,
)


def test_live_environment_is_blocked_by_default():
    with pytest.raises(LiveTradingBlocked):
        SafeAdapter("binance", TradingEnvironment.LIVE, AdapterCapabilities())


def test_testnet_adapter_is_allowed():
    adapter = SafeAdapter(
        "binance-testnet",
        TradingEnvironment.TESTNET,
        AdapterCapabilities(market_data=True, spot=True),
    )
    assert adapter.environment is TradingEnvironment.TESTNET
    assert adapter.capabilities.spot


def test_withdrawal_permission_is_rejected():
    account = AccountSnapshot("acct", TradingEnvironment.TESTNET, True, True)
    with pytest.raises(WithdrawalPermissionError):
        enforce_safe_account(account)


def test_trade_only_account_passes():
    account = AccountSnapshot("acct", TradingEnvironment.TESTNET, True, False)
    enforce_safe_account(account)


def test_symbol_info_validates_limits():
    info = SymbolInfo("BTCUSDT", "BTC", "USDT", 0.0001, 0.0001, 5.0)
    info.validate()


def test_invalid_symbol_limits_are_rejected():
    info = SymbolInfo("BTCUSDT", "BTC", "USDT", 0.0, 0.0001, 5.0)
    with pytest.raises(ValueError):
        info.validate()


def test_live_environment_requires_explicit_future_gate():
    with pytest.raises(LiveTradingBlocked):
        enforce_environment(TradingEnvironment.LIVE)
    enforce_environment(TradingEnvironment.LIVE, allow_live=True)


import json

from trading.execution import OrderRequest
from trading.market import BinanceMarketData


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _client():
    def opener(request, timeout):
        path = request.full_url.split("?", 1)[0]
        if path.endswith("/api/v3/exchangeInfo"):
            payload = {
                "symbols": [{
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "filters": [
                        {"filterType": "LOT_SIZE", "minQty": "0.001", "stepSize": "0.001"},
                        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                    ],
                }]
            }
        elif path.endswith("/api/v3/depth"):
            payload = {"bids": [["100", "1"]], "asks": [["101", "2"]]}
        else:
            raise AssertionError(path)
        return _Response(payload)

    return BinanceMarketData(timeout=3, opener=opener)


def test_binance_spot_testnet_adapter_exposes_normalized_symbol_filters():
    from trading.adapters import BinanceSpotTestnetAdapter

    adapter = BinanceSpotTestnetAdapter(_client())
    info = adapter.symbol_info("btcusdt")
    assert info.symbol == "BTCUSDT"
    assert info.min_quantity == 0.001
    assert info.quantity_step == 0.001
    assert info.min_notional == 10
    assert info.price_tick_size == 0.01


def test_binance_spot_testnet_adapter_is_read_only():
    from trading.adapters import BinanceSpotTestnetAdapter

    adapter = BinanceSpotTestnetAdapter(_client())
    with pytest.raises(LiveTradingBlocked, match="read-only"):
        adapter.submit_order(OrderRequest("BTCUSDT", "buy", 0.01, 100))


def test_binance_spot_testnet_adapter_has_no_withdrawal_capability():
    from trading.adapters import BinanceSpotTestnetAdapter

    adapter = BinanceSpotTestnetAdapter(_client())
    account = adapter.account_snapshot()
    assert account.can_trade is False
    assert account.can_withdraw is False


def test_binance_market_data_rejects_non_trading_symbol():
    def opener(request, timeout):
        return _Response({
            "symbols": [{
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "status": "BREAK",
                "filters": [
                    {"filterType": "LOT_SIZE", "minQty": "0.001", "stepSize": "0.001"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                ],
            }]
        })

    from trading.market import BinanceMarketData

    with pytest.raises(ValueError, match="not trading"):
        BinanceMarketData(opener=opener).exchange_info("BTCUSDT")


def test_binance_market_data_rejects_unusable_quantity_filter():
    def opener(request, timeout):
        return _Response({
            "symbols": [{
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "status": "TRADING",
                "filters": [
                    {"filterType": "LOT_SIZE", "minQty": "0", "stepSize": "0"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                ],
            }]
        })

    from trading.market import BinanceMarketData

    with pytest.raises(ValueError, match="quantity filters"):
        BinanceMarketData(opener=opener).exchange_info("BTCUSDT")
