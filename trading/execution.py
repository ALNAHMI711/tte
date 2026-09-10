"""Order routing boundary. Live routing is intentionally unavailable here."""
from __future__ import annotations

from dataclasses import dataclass

from .config import settings
from .paper import PaperBroker, PaperOrder
from .risk import RiskContext, RiskLimits, validate_order


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    price: float


class ExecutionEngine:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()
        self.paper = PaperBroker()

    def submit(self, request: OrderRequest, context: RiskContext) -> PaperOrder:
        notional = request.quantity * request.price
        validate_order(notional, self.limits, context)
        if settings.live_trading:
            raise RuntimeError("live execution is not implemented in this foundation")
        if not settings.paper_trading:
            raise RuntimeError("paper trading must be enabled")
        return self.paper.submit(request.symbol, request.side, request.quantity, request.price)
