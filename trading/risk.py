"""Hard, deterministic risk gates for every proposed order."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_order_notional: float = 100.0
    max_daily_loss: float = 25.0
    max_weekly_loss: float = 75.0
    max_open_exposure: float = 250.0
    max_slippage_bps: float = 50.0
    risk_per_trade_pct: float = 0.5
    max_correlation_exposure: float = 1.0


@dataclass(frozen=True)
class RiskContext:
    daily_loss: float = 0.0
    weekly_loss: float = 0.0
    open_exposure: float = 0.0
    estimated_slippage_bps: float = 0.0
    correlation_exposure: float = 0.0
    emergency_stop: bool = False


class RiskRejected(Exception):
    """Raised when the risk engine refuses an order."""


def validate_order(
    notional: float,
    limits: RiskLimits,
    ctx: RiskContext,
    *,
    account_equity: float | None = None,
    entry_price: float | None = None,
    stop_loss_price: float | None = None,
    quantity: float | None = None,
) -> None:
    if ctx.emergency_stop:
        raise RiskRejected("emergency stop is active")
    if notional <= 0:
        raise RiskRejected("order notional must be positive")
    if notional > limits.max_order_notional:
        raise RiskRejected("order exceeds max order notional")
    if ctx.daily_loss >= limits.max_daily_loss:
        raise RiskRejected("daily loss limit reached")
    if ctx.weekly_loss >= limits.max_weekly_loss:
        raise RiskRejected("weekly loss limit reached")
    if ctx.open_exposure + notional > limits.max_open_exposure:
        raise RiskRejected("open exposure limit reached")
    if ctx.estimated_slippage_bps > limits.max_slippage_bps:
        raise RiskRejected("estimated slippage is too high")
    if ctx.correlation_exposure + notional / limits.max_open_exposure > limits.max_correlation_exposure:
        raise RiskRejected("correlation exposure limit reached")

    if account_equity is not None:
        if account_equity <= 0:
            raise RiskRejected("account equity must be positive")
        if entry_price is None or stop_loss_price is None or quantity is None:
            raise RiskRejected("entry, stop loss and quantity are required for risk-per-trade validation")
        if entry_price <= 0 or stop_loss_price <= 0 or quantity <= 0:
            raise RiskRejected("entry, stop loss and quantity must be positive")
        risk_amount = abs(entry_price - stop_loss_price) * quantity
        risk_budget = account_equity * (limits.risk_per_trade_pct / 100)
        if risk_amount > risk_budget:
            raise RiskRejected("order exceeds risk-per-trade budget")
