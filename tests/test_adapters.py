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
