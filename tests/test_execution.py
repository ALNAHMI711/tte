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

    def capture(symbol: str, side: str, quantity: float, price: float, client_order_id=None):
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


def test_execution_enforces_half_percent_risk_budget_when_stop_is_supplied():
    engine = ExecutionEngine()
    with pytest.raises(RiskRejected, match="risk-per-trade"):
        engine.submit(
            OrderRequest("BTC/USDT", "buy", 0.01, 1000),
            RiskContext(),
            account_equity=1000,
            stop_loss_price=400,
        )


def test_execution_accepts_order_within_half_percent_risk_budget():
    engine = ExecutionEngine()
    order = engine.submit(
        OrderRequest("BTC/USDT", "buy", 0.01, 1000),
        RiskContext(),
        account_equity=1000,
        stop_loss_price=950,
    )
    assert order.status == "FILLED"


def test_execution_preserves_client_order_id_for_idempotent_paper_submission():
    engine = ExecutionEngine()
    request = OrderRequest("BTC/USDT", "buy", 0.01, 1000, client_order_id="client-001")

    first = engine.submit(request, RiskContext())
    second = engine.submit(request, RiskContext())

    assert second is first
    assert len(engine.paper.orders) == 1
    assert engine.paper.position("BTC/USDT").quantity == 0.01


def test_execution_uses_authoritative_portfolio_exposure_for_new_position():
    engine = ExecutionEngine(limits=__import__("trading.risk", fromlist=["RiskLimits"]).RiskLimits(max_open_exposure=100))
    engine.paper.submit("BTCUSDT", "buy", 0.08, 1000)

    with pytest.raises(RiskRejected, match="open exposure"):
        engine.submit(
            OrderRequest("ETHUSDT", "buy", 0.03, 1000),
            RiskContext(),
            market_prices={"BTCUSDT": 1000},
        )


def test_execution_allows_sell_when_it_reduces_portfolio_exposure():
    engine = ExecutionEngine(limits=__import__("trading.risk", fromlist=["RiskLimits"]).RiskLimits(max_open_exposure=100))
    engine.paper.submit("BTCUSDT", "buy", 0.10, 1000)

    order = engine.submit(
        OrderRequest("BTCUSDT", "sell", 0.05, 1000),
        RiskContext(),
        market_prices={"BTCUSDT": 1000},
    )

    assert order.status == "FILLED"
    assert engine.paper.position("BTCUSDT").quantity == 0.05
