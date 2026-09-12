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

    def submit(
        self,
        request: OrderRequest,
        context: RiskContext,
        symbol_info: object | None = None,
    ) -> PaperOrder:
        """Validate risk and exchange filters before any paper order is created.

        ``symbol_info`` is optional for backward compatibility with the original
        paper-only foundation. Production exchange paths must provide the
        provider-normalized symbol metadata so quantity, price, and notional are
        checked against the exchange filters before routing.
        """
        final_quantity = request.quantity
        final_price = request.price
        if symbol_info is not None:
            from .order_filters import normalize_and_validate_order

            normalized = normalize_and_validate_order(
                request.quantity,
                request.price,
                symbol_info,
            )
            final_quantity = float(normalized.quantity)
            final_price = float(normalized.price)

        notional = final_quantity * final_price
        validate_order(notional, self.limits, context)
        if settings.live_trading:
            raise RuntimeError("live execution is not implemented in this foundation")
        if not settings.paper_trading:
            raise RuntimeError("paper trading must be enabled")
        return self.paper.submit(
            request.symbol,
            request.side,
            final_quantity,
            final_price,
        )
