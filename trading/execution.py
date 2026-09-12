"""Order routing boundary. Live routing is intentionally unavailable here."""
from __future__ import annotations

from dataclasses import dataclass

from .binance_preflight import BinancePreflightReport
from .config import settings
from .kill_switch import KillSwitch
from .paper import PaperBroker, PaperOrder
from .risk import RiskContext, RiskLimits, RiskRejected, validate_order


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    price: float


class ExecutionEngine:
    def __init__(
        self,
        limits: RiskLimits | None = None,
        kill_switch: KillSwitch | None = None,
        live_preflight: BinancePreflightReport | None = None,
    ) -> None:
        self.limits = limits or RiskLimits()
        self.paper = PaperBroker()
        self.kill_switch = kill_switch or KillSwitch()
        self.live_preflight = live_preflight

    def submit(
        self,
        request: OrderRequest,
        context: RiskContext,
        symbol_info: object | None = None,
    ) -> PaperOrder:
        """Validate hard safety gates before any order is created.

        The kill switch blocks only new orders; it never liquidates existing
        positions. ``symbol_info`` is optional for backward compatibility with
        the original paper-only foundation. LIVE mode additionally requires a
        previously evaluated, passing Binance preflight report. Live order
        routing remains intentionally unavailable until a real exchange adapter
        is implemented and separately tested.
        """
        kill_state = self.kill_switch.snapshot()
        if kill_state.enabled:
            raise RiskRejected(f"kill switch is active: {kill_state.reason}")

        if settings.live_trading:
            if self.live_preflight is None:
                raise RuntimeError("LIVE execution requires a completed Binance preflight")
            if not self.live_preflight.passed:
                raise RiskRejected("LIVE execution blocked by failed Binance preflight")

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
