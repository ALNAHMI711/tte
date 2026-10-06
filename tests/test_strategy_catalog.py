import pytest

from trading.strategy import EmaCrossStrategy, StrategyAction, StrategyCandle, StrategyContext
from trading.strategy_catalog import STRATEGY_CATALOG, build_order_request


def candles(closes):
    return tuple(StrategyCandle(i, v, v, v, v, 100) for i, v in enumerate(closes))


def test_catalog_contains_only_registered_strategy():
    assert [item.id for item in STRATEGY_CATALOG] == ["ema_cross_20_50"]


def test_builder_returns_none_for_hold():
    strategy = EmaCrossStrategy(2, 3)
    context = StrategyContext("BTCUSDT", candles([10, 11]), False)
    assert build_order_request(strategy, context, quantity=1, price=100) is None


def test_builder_translates_long_signal_without_execution():
    strategy = EmaCrossStrategy(2, 3)
    context = StrategyContext("BTCUSDT", candles([10, 9, 8, 12, 14]), False)
    request = build_order_request(
        strategy, context, quantity=0.01, price=1000, client_order_id="ema-001"
    )
    assert request is not None
    assert request.side == "buy"
    assert request.quantity == 0.01
    assert request.client_order_id == "ema-001"


def test_builder_translates_exit_signal():
    strategy = EmaCrossStrategy(2, 3)
    context = StrategyContext("BTCUSDT", candles([14, 13, 12, 9, 8]), True)
    request = build_order_request(strategy, context, quantity=0.02, price=900)
    assert request is not None
    assert request.side == "sell"


def test_builder_rejects_invalid_quantity():
    class AlwaysLong:
        name = "test"
        def evaluate(self, context):
            return StrategyAction.ENTER_LONG

    context = StrategyContext("BTCUSDT", candles([10]), False)
    with pytest.raises(ValueError, match="quantity"):
        build_order_request(AlwaysLong(), context, quantity=0, price=100)
