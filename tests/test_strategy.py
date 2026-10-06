from trading.strategy import EmaCrossStrategy, StrategyAction, StrategyCandle, StrategyContext


def candles(closes):
    return tuple(StrategyCandle(i, v, v, v, v, 100) for i, v in enumerate(closes))


def test_strategy_holds_during_warmup():
    strategy = EmaCrossStrategy(2, 3)
    assert strategy.evaluate(StrategyContext("BTCUSDT", candles([10, 11]), False)) is StrategyAction.HOLD


def test_strategy_enters_long_only_on_bullish_cross():
    strategy = EmaCrossStrategy(2, 3)
    result = strategy.evaluate(StrategyContext("BTCUSDT", candles([10, 9, 8, 7, 20]), False))
    assert result is StrategyAction.ENTER_LONG


def test_strategy_exits_long_on_bearish_state():
    strategy = EmaCrossStrategy(2, 3)
    result = strategy.evaluate(StrategyContext("BTCUSDT", candles([14, 13, 12, 9, 8]), True))
    assert result is StrategyAction.EXIT_LONG


def test_strategy_does_not_enter_when_position_exists():
    strategy = EmaCrossStrategy(2, 3)
    result = strategy.evaluate(StrategyContext("BTCUSDT", candles([10, 9, 8, 12, 14]), True))
    assert result is StrategyAction.HOLD
