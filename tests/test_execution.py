from decimal import Decimal

import pytest

from trading.adapters import AccountSnapshot, SymbolInfo
from trading.execution import ExecutionEngine, OrderRequest
from trading.adapters import TradingEnvironment
from trading.kill_switch import KillSwitch
from trading.order_filters import OrderFilterError
from trading.risk import RiskContext, RiskRejected


SIGNAL_SCORE = 90.0
REWARD_RISK = 2.5
STOP_LOSS = 950.0


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
    order = engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext(), signal_score=SIGNAL_SCORE, reward_risk_ratio=REWARD_RISK, stop_loss_price=STOP_LOSS)
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
        signal_score=SIGNAL_SCORE,
        reward_risk_ratio=REWARD_RISK,
        stop_loss_price=STOP_LOSS,
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
            signal_score=SIGNAL_SCORE,
            reward_risk_ratio=REWARD_RISK,
            stop_loss_price=STOP_LOSS,
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
        engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext(), signal_score=SIGNAL_SCORE, reward_risk_ratio=REWARD_RISK, stop_loss_price=STOP_LOSS)

    assert called is False


def test_execution_resumes_new_orders_after_kill_switch_deactivation() -> None:
    kill_switch = KillSwitch()
    kill_switch.activate("temporary stop")
    engine = ExecutionEngine(kill_switch=kill_switch)
    kill_switch.deactivate()

    order = engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext(), signal_score=SIGNAL_SCORE, reward_risk_ratio=REWARD_RISK, stop_loss_price=STOP_LOSS)

    assert order.status == "FILLED"


def test_execution_preserves_context_emergency_stop_gate() -> None:
    engine = ExecutionEngine()

    with pytest.raises(RiskRejected, match="emergency stop"):
        engine.submit(
            OrderRequest("BTC/USDT", "buy", 0.01, 1000),
            RiskContext(emergency_stop=True),
            signal_score=SIGNAL_SCORE,
            reward_risk_ratio=REWARD_RISK,
            stop_loss_price=STOP_LOSS,
        )


def test_execution_enforces_half_percent_risk_budget_when_stop_is_supplied():
    engine = ExecutionEngine()
    with pytest.raises(RiskRejected, match="risk-per-trade"):
        engine.submit(
            OrderRequest("BTC/USDT", "buy", 0.01, 1000),
            RiskContext(),
            account_equity=1000,
            stop_loss_price=400,
            signal_score=SIGNAL_SCORE,
            reward_risk_ratio=REWARD_RISK,
        )


def test_execution_accepts_order_within_half_percent_risk_budget():
    engine = ExecutionEngine()
    order = engine.submit(
        OrderRequest("BTC/USDT", "buy", 0.01, 1000),
        RiskContext(),
        account_equity=1000,
        stop_loss_price=STOP_LOSS,
        signal_score=SIGNAL_SCORE,
        reward_risk_ratio=REWARD_RISK,
    )
    assert order.status == "FILLED"


def test_execution_preserves_client_order_id_for_idempotent_paper_submission():
    engine = ExecutionEngine()
    request = OrderRequest("BTC/USDT", "buy", 0.01, 1000, client_order_id="client-001")

    first = engine.submit(request, RiskContext(), signal_score=SIGNAL_SCORE, reward_risk_ratio=REWARD_RISK, stop_loss_price=STOP_LOSS)
    second = engine.submit(request, RiskContext(), signal_score=SIGNAL_SCORE, reward_risk_ratio=REWARD_RISK, stop_loss_price=STOP_LOSS)

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
            signal_score=SIGNAL_SCORE,
            reward_risk_ratio=REWARD_RISK,
            stop_loss_price=STOP_LOSS,
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


def test_execution_requires_market_prices_when_positions_exist():
    engine = ExecutionEngine()
    engine.paper.submit("BTCUSDT", "buy", 0.01, 1000)

    with pytest.raises(RiskRejected, match="market prices"):
        engine.submit(
            OrderRequest("ETHUSDT", "buy", 0.01, 1000),
            RiskContext(),
        )


def test_execution_rejects_invalid_side_before_exposure_calculation():
    engine = ExecutionEngine()
    engine.paper.submit("BTCUSDT", "buy", 0.01, 1000)

    with pytest.raises(RiskRejected, match="side must be buy or sell"):
        engine.submit(
            OrderRequest("ETHUSDT", "hold", 0.01, 1000),
            RiskContext(),
            market_prices={"BTCUSDT": 1000},
            signal_score=SIGNAL_SCORE,
            reward_risk_ratio=REWARD_RISK,
            stop_loss_price=STOP_LOSS,
        )


class _Adapter:
    from trading.adapters import AdapterCapabilities, AccountSnapshot, SymbolInfo, TradingEnvironment

    environment = TradingEnvironment.TESTNET
    capabilities = AdapterCapabilities(market_data=True, spot=True)

    def __init__(self):
        self.calls = []

    def account_snapshot(self):
        self.calls.append("account")
        return AccountSnapshot("paper-source", TradingEnvironment.TESTNET, False, False)

    def symbol_info(self, symbol):
        self.calls.append(("symbol_info", symbol))
        return SYMBOL

    def ticker(self, symbol):
        self.calls.append(("ticker", symbol))
        return (99.0, 101.0)

    def submit_order(self, request):
        self.calls.append(("submit_order", request))
        raise AssertionError("adapter order routing must never be called")


def test_execution_adapter_path_is_read_only_and_routes_to_paper():
    engine = ExecutionEngine()
    adapter = _Adapter()

    order = engine.submit_from_adapter(
        OrderRequest("BTCUSDT", "buy", 0.01, 1000),
        RiskContext(),
        adapter,
        signal_score=SIGNAL_SCORE,
        reward_risk_ratio=REWARD_RISK,
        stop_loss_price=STOP_LOSS,
    )

    assert order.status == "FILLED"
    assert engine.paper.position("BTCUSDT").quantity == 0.01
    assert not any(isinstance(call, tuple) and call[0] == "submit_order" for call in adapter.calls)


def test_execution_adapter_path_fetches_marks_for_existing_positions():
    engine = ExecutionEngine()
    engine.paper.submit("BTCUSDT", "buy", 0.01, 1000)
    adapter = _Adapter()

    order = engine.submit_from_adapter(
        OrderRequest("BTCUSDT", "sell", 0.005, 1000),
        RiskContext(),
        adapter,
        signal_score=SIGNAL_SCORE,
        reward_risk_ratio=REWARD_RISK,
        stop_loss_price=STOP_LOSS,
    )

    assert order.status == "FILLED"
    assert engine.paper.position("BTCUSDT").quantity == 0.005
    assert ("ticker", "BTCUSDT") in adapter.calls


def test_execution_adapter_path_applies_exchange_filters_before_paper():
    engine = ExecutionEngine()
    adapter = _Adapter()

    with pytest.raises(OrderFilterError, match="notional"):
        engine.submit_from_adapter(
            OrderRequest("BTCUSDT", "buy", 0.001, 100),
            RiskContext(),
            adapter,
        )

    assert engine.paper.orders == []


def test_execution_adapter_path_rejects_live_before_adapter_submission():
    class LiveAdapter(_Adapter):
        environment = TradingEnvironment.LIVE

    engine = ExecutionEngine()
    adapter = LiveAdapter()

    with pytest.raises(RuntimeError, match="LIVE adapter routing"):
        engine.submit_from_adapter(
            OrderRequest("BTCUSDT", "buy", 0.01, 1000),
            RiskContext(),
            adapter,
        )
    assert adapter.calls == []

def test_execution_strict_risk_requires_signal_score_before_paper_submission():
    engine = ExecutionEngine()
    with pytest.raises(RiskRejected, match="signal score"):
        engine.submit(
            OrderRequest("BTC/USDT", "buy", 0.01, 1000),
            RiskContext(),
            stop_loss_price=STOP_LOSS,
            reward_risk_ratio=REWARD_RISK,
        )
    assert engine.paper.orders == ()


def test_execution_strict_risk_requires_reward_risk_before_paper_submission():
    engine = ExecutionEngine()
    with pytest.raises(RiskRejected, match="reward-risk"):
        engine.submit(
            OrderRequest("BTC/USDT", "buy", 0.01, 1000),
            RiskContext(),
            stop_loss_price=STOP_LOSS,
            signal_score=SIGNAL_SCORE,
        )
    assert engine.paper.orders == ()


def test_execution_strict_risk_requires_stop_loss_before_paper_submission():
    engine = ExecutionEngine()
    with pytest.raises(RiskRejected, match="protective"):
        engine.submit(
            OrderRequest("BTC/USDT", "buy", 0.01, 1000),
            RiskContext(),
            signal_score=SIGNAL_SCORE,
            reward_risk_ratio=REWARD_RISK,
        )
    assert engine.paper.orders == ()


def test_execution_enforces_authoritative_max_open_positions():
    from trading.risk import RiskLimits

    engine = ExecutionEngine(limits=RiskLimits(max_open_positions=1))
    engine.paper.submit("BTCUSDT", "buy", 0.01, 1000)

    with pytest.raises(RiskRejected, match="maximum open positions"):
        engine.submit(
            OrderRequest("ETHUSDT", "buy", 0.01, 1000),
            RiskContext(),
            market_prices={"BTCUSDT": 1000},
            signal_score=SIGNAL_SCORE,
            reward_risk_ratio=REWARD_RISK,
            stop_loss_price=STOP_LOSS,
        )
    assert len(engine.paper.orders) == 1


def test_execution_idempotency_cannot_bypass_missing_signal():
    engine = ExecutionEngine()
    request = OrderRequest("BTCUSDT", "buy", 0.01, 1000, client_order_id="strict-001")
    first = engine.submit(
        request,
        RiskContext(),
        signal_score=SIGNAL_SCORE,
        reward_risk_ratio=REWARD_RISK,
        stop_loss_price=STOP_LOSS,
    )

    with pytest.raises(RiskRejected, match="signal score"):
        engine.submit(
            request,
            RiskContext(),
            reward_risk_ratio=REWARD_RISK,
            stop_loss_price=STOP_LOSS,
        )
    assert first.status == "FILLED"
