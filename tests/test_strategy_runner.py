from trading.execution import ExecutionEngine
from trading.risk import RiskContext, RiskRejected
from trading.strategy import EmaCrossStrategy, StrategyCandle, StrategyContext
from trading.strategy_runner import StrategyRunner


def candles(closes):
    return tuple(StrategyCandle(i, v, v, v, v, 100) for i, v in enumerate(closes))


def test_runner_does_not_execute_hold():
    engine = ExecutionEngine()
    runner = StrategyRunner(engine, EmaCrossStrategy(2, 3))
    result = runner.run(
        StrategyContext("BTCUSDT", candles([10, 11]), False),
        RiskContext(),
        quantity=0.01,
        price=1000,
    )
    assert result.action == "hold"
    assert result.order is None
    assert engine.paper.orders == []


def test_runner_routes_long_signal_through_execution():
    engine = ExecutionEngine()
    runner = StrategyRunner(engine, EmaCrossStrategy(2, 3))
    result = runner.run(
        StrategyContext("BTCUSDT", candles([10, 9, 8, 7, 20]), False),
        RiskContext(),
        quantity=0.01,
        price=1000,
        client_order_id="runner-001",
    )
    assert result.action == "enter_long"
    assert result.order is not None
    assert result.order.side == "buy"
    assert engine.paper.position("BTCUSDT").quantity == 0.01


def test_runner_cannot_bypass_risk_gate():
    engine = ExecutionEngine()
    runner = StrategyRunner(engine, EmaCrossStrategy(2, 3))
    result_context = StrategyContext("BTCUSDT", candles([10, 9, 8, 7, 20]), False)

    try:
        runner.run(
            result_context,
            RiskContext(),
            quantity=0.01,
            price=1000,
            account_equity=1000,
            stop_loss_price=400,
        )
    except RiskRejected as exc:
        assert "risk-per-trade" in str(exc)
    else:
        raise AssertionError("strategy runner bypassed risk validation")

    assert engine.paper.orders == []


def test_runner_uses_exit_signal_for_existing_position():
    engine = ExecutionEngine()
    runner = StrategyRunner(engine, EmaCrossStrategy(2, 3))
    engine.paper.submit("BTCUSDT", "buy", 0.02, 900)

    result = runner.run(
        StrategyContext("BTCUSDT", candles([14, 13, 12, 9, 8]), True),
        RiskContext(),
        quantity=0.02,
        price=900,
    )
    assert result.action == "exit_long"
    assert result.order is not None
    assert result.order.side == "sell"
    assert engine.paper.position("BTCUSDT") is None


class OneShotStrategy:
    def __init__(self):
        self.calls = 0

    def evaluate(self, context):
        self.calls += 1
        from trading.strategy import StrategyAction
        return StrategyAction.ENTER_LONG if self.calls == 1 else StrategyAction.HOLD


def test_runner_evaluates_strategy_only_once():
    engine = ExecutionEngine()
    strategy = OneShotStrategy()
    runner = StrategyRunner(engine, strategy)

    result = runner.run(
        StrategyContext("BTCUSDT", candles([10, 9, 8, 7, 20]), False),
        RiskContext(),
        quantity=0.01,
        price=1000,
    )

    assert strategy.calls == 1
    assert result.action == "enter_long"
    assert result.order is not None
