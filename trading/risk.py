"""Hard safety gates for every proposed order."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_order_notional: float = 100.0
    max_daily_loss: float = 25.0
    max_open_exposure: float = 250.0
    max_slippage_bps: float = 50.0


@dataclass(frozen=True)
class RiskContext:
    daily_loss: float = 0.0
    open_exposure: float = 0.0
    estimated_slippage_bps: float = 0.0
    emergency_stop: bool = False


class RiskRejected(Exception):
    """Raised when the risk engine refuses an order."""


def validate_order(notional: float, limits: RiskLimits, ctx: RiskContext) -> None:
    if ctx.emergency_stop:
        raise RiskRejected("emergency stop is active")
    if notional <= 0:
        raise RiskRejected("order notional must be positive")
    if notional > limits.max_order_notional:
        raise RiskRejected("order exceeds max order notional")
    if ctx.daily_loss >= limits.max_daily_loss:
        raise RiskRejected("daily loss limit reached")
    if ctx.open_exposure + notional > limits.max_open_exposure:
        raise RiskRejected("open exposure limit reached")
    if ctx.estimated_slippage_bps > limits.max_slippage_bps:
        raise RiskRejected("estimated slippage is too high")
