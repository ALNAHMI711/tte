"""Derived risk context from the authoritative paper portfolio ledger."""
from __future__ import annotations

from dataclasses import dataclass
from .paper import PaperBroker


@dataclass(frozen=True)
class PortfolioExposure:
    gross_notional: float
    symbols: tuple[str, ...]


def portfolio_exposure(broker: PaperBroker, prices: dict[str, float]) -> PortfolioExposure:
    """Value current paper positions at supplied market prices.

    Missing prices are ignored rather than guessed. This is deliberately
    read-only; the broker remains the source of truth for position quantities.
    """
    gross = 0.0
    symbols: list[str] = []
    for position in broker.positions():
        price = prices.get(position.symbol)
        if price is None:
            continue
        if price <= 0:
            raise ValueError(f"price for {position.symbol} must be positive")
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
