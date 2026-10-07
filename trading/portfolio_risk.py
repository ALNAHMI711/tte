"""Derived risk context from the authoritative paper portfolio ledger."""
from __future__ import annotations

from dataclasses import dataclass
import math

from .paper import PaperBroker


@dataclass(frozen=True)
class PortfolioExposure:
    gross_notional: float
    symbols: tuple[str, ...]


def portfolio_exposure(broker: PaperBroker, prices: dict[str, float]) -> PortfolioExposure:
    """Value current paper positions at supplied market prices.

    Every open position must have a valid mark price. Silently omitting a
    position would understate exposure and could bypass the exposure limit.
    This is deliberately read-only; the broker remains the source of truth.
    """
    gross = 0.0
    symbols: list[str] = []
    for position in broker.positions():
        price = prices.get(position.symbol)
        if price is None:
            raise ValueError(f"missing market price for {position.symbol}")
        if not math.isfinite(price) or price <= 0:
            raise ValueError(f"price for {position.symbol} must be finite and positive")
        gross += position.quantity * price
        symbols.append(position.symbol)
    return PortfolioExposure(gross_notional=gross, symbols=tuple(symbols))


def risk_context_from_portfolio(
    broker: PaperBroker,
    prices: dict[str, float],
    *,
    daily_loss: float = 0.0,
    weekly_loss: float = 0.0,
    estimated_slippage_bps: float = 0.0,
    correlation_exposure: float = 0.0,
    emergency_stop: bool = False,
):
    """Build a RiskContext using live paper positions instead of caller input."""
    from .risk import RiskContext

    exposure = portfolio_exposure(broker, prices)
    return RiskContext(
        daily_loss=daily_loss,
        weekly_loss=weekly_loss,
        open_exposure=exposure.gross_notional,
        estimated_slippage_bps=estimated_slippage_bps,
        correlation_exposure=correlation_exposure,
        emergency_stop=emergency_stop,
    )
