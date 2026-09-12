from decimal import Decimal

import pytest

from trading.adapters import SymbolInfo
from trading.execution import ExecutionEngine, OrderRequest
from trading.kill_switch import KillSwitch
from trading.order_filters import OrderFilterError
from trading.risk import RiskContext, RiskRejected


SYMBOL = SymbolInfo(
    symbol="BTCUSDT",
    base_asset="BTC",
    quote_asset="USDT",
    min_quantity=Decimal("0.001"),
    quantity_step=Decimal("0.001"),
    min_notional=Decimal("10"),
    price_tick_size=Decimal("0.01"),
)


def test_execution_uses_paper_broker() -> None:
    engine = ExecutionEngine()
    order = engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())
    assert order.status == "FILLED"
    assert order.id.startswith("paper-")


def test_execution_routes_exchange_normalized_values() -> None:
    engine = ExecutionEngine()
    captured: dict[str, float] = {}

    def capture(symbol: str, side: str, quantity: float, price: float):
        captured.update(symbol=symbol, side=side, quantity=quantity, price=price)
        return type("Order", (), {"status": "FILLED", "id": "paper-captured"})()

    engine.paper.submit = capture  # type: ignore[method-assign]
    order = engine.submit(
        OrderRequest("BTC/USDT", "buy", 0.0019, 10000.1234),
        RiskContext(),
        SYMBOL,
    )

    assert order.status == "FILLED"
    assert captured == {
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 0.001,
        "price": 10000.12,
    }


def test_execution_rejects_minimum_notional_before_paper_submission() -> None:
    engine = ExecutionEngine()
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("paper broker must not receive an invalid order")

    engine.paper.submit = fail_if_called  # type: ignore[method-assign]

    with pytest.raises(OrderFilterError, match="notional"):
        engine.submit(
            OrderRequest("BTC/USDT", "buy", 0.0019, 100),
            RiskContext(),
            SYMBOL,
        )

    assert called is False


def test_execution_kill_switch_blocks_new_orders_before_paper_submission() -> None:
    kill_switch = KillSwitch()
    kill_switch.activate("operator requested stop")
    engine = ExecutionEngine(kill_switch=kill_switch)
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("paper broker must not receive an order while kill switch is active")

    engine.paper.submit = fail_if_called  # type: ignore[method-assign]

    with pytest.raises(RiskRejected, match="operator requested stop"):
        engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())

    assert called is False


def test_execution_resumes_new_orders_after_kill_switch_deactivation() -> None:
    kill_switch = KillSwitch()
    kill_switch.activate("temporary stop")
    engine = ExecutionEngine(kill_switch=kill_switch)
    kill_switch.deactivate()

    order = engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())

    assert order.status == "FILLED"


def test_execution_preserves_context_emergency_stop_gate() -> None:
    engine = ExecutionEngine()

    with pytest.raises(RiskRejected, match="emergency stop"):
        engine.submit(
            OrderRequest("BTC/USDT", "buy", 0.01, 1000),
            RiskContext(emergency_stop=True),
        )
