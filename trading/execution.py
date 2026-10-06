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
    client_order_id: str | None = None


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
        *,
        account_equity: float | None = None,
        stop_loss_price: float | None = None,
        market_prices: dict[str, float] | None = None,
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
        risk_context = context
        if market_prices is not None:
            from .portfolio_risk import portfolio_exposure

            exposure = portfolio_exposure(self.paper, market_prices)
            risk_context = RiskContext(
                daily_loss=context.daily_loss,
                weekly_loss=context.weekly_loss,
                open_exposure=exposure.gross_notional,
                estimated_slippage_bps=context.estimated_slippage_bps,
                correlation_exposure=context.correlation_exposure,
                emergency_stop=context.emergency_stop,
            )
        normalized_side = request.side.strip().lower()
        exposure_delta = notional if normalized_side == "buy" else -notional
        validate_order(
            notional,
            self.limits,
            risk_context,
            account_equity=account_equity,
            entry_price=final_price,
            stop_loss_price=stop_loss_price,
            quantity=final_quantity,
            side=request.side,
            exposure_delta=exposure_delta,
        )
        if settings.live_trading:
            raise RuntimeError("live execution is not implemented in this foundation")
        if not settings.paper_trading:
            raise RuntimeError("paper trading must be enabled")
        return self.paper.submit(
            request.symbol,
            request.side,
            final_quantity,
            final_price,
            request.client_order_id,
        )
