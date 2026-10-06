from trading.backtest import BacktestCandle, BacktestConfig, BacktestEngine, SmaCrossStrategy, Signal


def candles_from_closes(closes):
    return [
        BacktestCandle(time=i, open=value, high=value, low=value, close=value, volume=100)
        for i, value in enumerate(closes)
    ]


def test_backtest_rejects_empty_input():
    try:
        BacktestEngine().run([], SmaCrossStrategy(2, 3))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_backtest_is_deterministic_and_does_not_need_exchange():
    candles = candles_from_closes([10, 10, 10, 11, 12, 13, 12, 11, 10])
    engine = BacktestEngine(BacktestConfig(initial_cash=1000, fee_rate=0))
    strategy = SmaCrossStrategy(2, 3)
    first = engine.run(candles, strategy)
    second = engine.run(candles, strategy)
    assert first == second
    assert first.initial_cash == 1000
    assert first.final_equity > 0


def test_strategy_has_warmup_hold_and_valid_signals():
    strategy = SmaCrossStrategy(2, 3)
    candles = candles_from_closes([10, 11, 12, 13, 14])
    assert strategy.signal(candles, 0) is Signal.HOLD
    assert strategy.signal(candles, 1) is Signal.HOLD
    assert strategy.signal(candles, 2) in {Signal.HOLD, Signal.LONG, Signal.FLAT}


def test_backtest_records_costs_and_drawdown():
    candles = candles_from_closes([10, 11, 12, 11, 10, 9, 8])
    result = BacktestEngine(BacktestConfig(initial_cash=1000, fee_rate=0.001, slippage_bps=5)).run(
        candles, SmaCrossStrategy(2, 3)
    )
    assert result.final_equity > 0
    assert result.max_drawdown_pct >= 0
    assert all(trade.fees >= 0 for trade in result.trades)
    assert all(trade.net_pnl == trade.gross_pnl - trade.fees for trade in result.trades)


def test_backtest_executes_signal_on_next_bar_open_not_signal_bar_close():
    candles = [
        BacktestCandle(0, 10, 10, 10, 10, 100),
        BacktestCandle(1, 20, 20, 20, 20, 100),
        BacktestCandle(2, 20, 20, 20, 20, 100),
    ]

    class BuyAtFirstClose:
        name = "test"
        def signal(self, candles, index):
            return Signal.LONG if index == 0 else Signal.HOLD

    result = BacktestEngine(BacktestConfig(initial_cash=1000, fee_rate=0)).run(candles, BuyAtFirstClose())
    assert len(result.trades) == 1
    assert result.trades[0].entry_time == 1
    assert result.trades[0].entry_price == 20
