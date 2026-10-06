"""Strategy catalog and safe signal-to-order translation."""
from __future__ import annotations

from dataclasses import dataclass

from .execution import OrderRequest
from .strategy import RuntimeStrategy, StrategyAction, StrategyContext


@dataclass(frozen=True)
class StrategyDefinition:
    id: str
    name: str
    description: str


STRATEGY_CATALOG: tuple[StrategyDefinition, ...] = (
    StrategyDefinition(
        id="ema_cross_20_50",
        name="EMA 20/50 Cross",
        description="Long-only EMA cross signal source.",
    ),
)


def build_order_request(
    strategy: RuntimeStrategy,
    context: StrategyContext,
    *,
    quantity: float,
    price: float,
    client_order_id: str | None = None,
) -> OrderRequest | None:
    """Translate a strategy signal into an order request; never executes it.

    EXIT_LONG uses the current position quantity. ENTER_LONG requires an
    explicit quantity supplied by the risk/orchestration layer.
    """
    action = strategy.evaluate(context)
    if action is StrategyAction.HOLD:
        return None

    if price <= 0:
        raise ValueError("price must be positive")

    if action is StrategyAction.ENTER_LONG:
        if context.has_long_position:
            return None
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        return OrderRequest(
            symbol=context.symbol,
            side="buy",
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )

    if action is StrategyAction.EXIT_LONG:
        if not context.has_long_position:
            return None
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        return OrderRequest(
            symbol=context.symbol,
            side="sell",
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )

    raise ValueError(f"unsupported strategy action: {action}")
