"""Safe runtime orchestration: strategy signals flow through risk and execution."""
from __future__ import annotations

from dataclasses import dataclass

from .execution import ExecutionEngine
from .risk import RiskContext
from .strategy import RuntimeStrategy, StrategyContext
from .strategy_catalog import build_order_request_from_action


@dataclass(frozen=True)
class StrategyRunResult:
    action: str
    order: object | None


class StrategyRunner:
    """Evaluate one strategy cycle and route only approved orders to execution.

    The runner has no exchange access of its own. Every non-HOLD signal is
    translated into an OrderRequest and then passed to ExecutionEngine, where
    kill-switch, symbol filters, risk limits, and paper/live gates remain
    authoritative.
    """

    def __init__(self, execution: ExecutionEngine, strategy: RuntimeStrategy) -> None:
        self.execution = execution
        self.strategy = strategy

    def run(
        self,
        context: StrategyContext,
        risk_context: RiskContext,
        *,
        quantity: float,
        price: float,
        client_order_id: str | None = None,
        account_equity: float | None = None,
        stop_loss_price: float | None = None,
        symbol_info: object | None = None,
        market_prices: dict[str, float] | None = None,
        signal_score: float | None = None,
        reward_risk_ratio: float | None = None,
    ) -> StrategyRunResult:
        action = self.strategy.evaluate(context)
        request = build_order_request_from_action(
            action,
            context,
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )
        if request is None:
            return StrategyRunResult(action=action.value, order=None)

        order = self.execution.submit(
            request,
            risk_context,
            symbol_info,
            account_equity=account_equity,
            stop_loss_price=stop_loss_price,
            market_prices=market_prices,
            signal_score=signal_score,
            reward_risk_ratio=reward_risk_ratio,
        )
        return StrategyRunResult(action=action.value, order=order)
