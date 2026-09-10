from trading.execution import ExecutionEngine, OrderRequest
from trading.risk import RiskContext


def test_execution_uses_paper_broker() -> None:
    engine = ExecutionEngine()
    order = engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())
    assert order.status == "FILLED"
    assert order.id.startswith("paper-")
