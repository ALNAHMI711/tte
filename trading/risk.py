"""Hard, deterministic risk gates for every proposed order."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RiskLimits:
    max_order_notional: float = 100.0
    max_daily_loss: float = 25.0
    max_weekly_loss: float = 75.0
    max_open_exposure: float = 250.0
    max_slippage_bps: float = 50.0
    risk_per_trade_pct: float = 0.5
    max_correlation_exposure: float = 250.0
    max_open_positions: int = 5
    min_signal_score: float = 85.0
    min_reward_risk: float = 2.0

    def __post_init__(self) -> None:
        fields = (
            ("max_order_notional", self.max_order_notional),
            ("max_daily_loss", self.max_daily_loss),
            ("max_weekly_loss", self.max_weekly_loss),
            ("max_open_exposure", self.max_open_exposure),
            ("max_slippage_bps", self.max_slippage_bps),
            ("max_correlation_exposure", self.max_correlation_exposure),
            ("min_signal_score", self.min_signal_score),
            ("min_reward_risk", self.min_reward_risk),
        )
        for name, value in fields:
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a finite positive number")
        if not math.isfinite(self.risk_per_trade_pct) or not 0 < self.risk_per_trade_pct <= 100:
            raise ValueError("risk_per_trade_pct must be finite, greater than 0 and at most 100")
        if not isinstance(self.max_open_positions, int) or isinstance(self.max_open_positions, bool) or self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be a positive integer")


@dataclass(frozen=True)
class RiskContext:
    daily_loss: float = 0.0
    weekly_loss: float = 0.0
    open_exposure: float = 0.0
    estimated_slippage_bps: float = 0.0
    correlation_exposure: float = 0.0
    open_positions: int = 0
    emergency_stop: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("daily_loss", self.daily_loss),
            ("weekly_loss", self.weekly_loss),
            ("open_exposure", self.open_exposure),
            ("estimated_slippage_bps", self.estimated_slippage_bps),
            ("correlation_exposure", self.correlation_exposure),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite non-negative number")
        if not isinstance(self.open_positions, int) or isinstance(self.open_positions, bool) or self.open_positions < 0:
            raise ValueError("open_positions must be a non-negative integer")


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
    side: str | None = None,
    exposure_delta: float | None = None,
    signal_score: float | None = 85.0,
    reward_risk_ratio: float | None = 2.0,
) -> None:
    if ctx.emergency_stop:
        raise RiskRejected("emergency stop is active")
    if not math.isfinite(notional) or notional <= 0:
        raise RiskRejected("order notional must be positive")
    if signal_score is not None and not math.isfinite(signal_score):
        raise RiskRejected("signal score must be finite")
    if signal_score is None or signal_score < limits.min_signal_score:
        raise RiskRejected("signal score is below minimum")
    if reward_risk_ratio is not None and not math.isfinite(reward_risk_ratio):
        raise RiskRejected("reward-risk ratio must be finite")
    if reward_risk_ratio is None or reward_risk_ratio < limits.min_reward_risk:
        raise RiskRejected("reward-risk ratio is below minimum")
    if notional > limits.max_order_notional:
        raise RiskRejected("order exceeds max order notional")
    if ctx.daily_loss >= limits.max_daily_loss:
        raise RiskRejected("daily loss limit reached")
    if ctx.weekly_loss >= limits.max_weekly_loss:
        raise RiskRejected("weekly loss limit reached")
    if (exposure_delta is None or exposure_delta > 0) and ctx.open_positions >= limits.max_open_positions:
        raise RiskRejected("maximum open positions reached")
    projected_exposure = ctx.open_exposure + (notional if exposure_delta is None else exposure_delta)
    if projected_exposure < 0:
        raise RiskRejected("projected open exposure cannot be negative")
    if projected_exposure > limits.max_open_exposure:
        raise RiskRejected("open exposure limit reached")
    projected_correlation = ctx.correlation_exposure + (notional if exposure_delta is None else max(exposure_delta, 0.0))
    if projected_correlation > limits.max_correlation_exposure:
        raise RiskRejected("correlation exposure limit reached")
    if ctx.estimated_slippage_bps > limits.max_slippage_bps:
        raise RiskRejected("estimated slippage is too high")

    if side is not None and entry_price is not None and stop_loss_price is not None:
        normalized_side = side.strip().lower()
        if normalized_side not in {"buy", "sell"}:
            raise RiskRejected("side must be buy or sell")
        if not math.isfinite(entry_price) or entry_price <= 0:
            raise RiskRejected("entry price must be positive")
        if not math.isfinite(stop_loss_price) or stop_loss_price <= 0:
            raise RiskRejected("stop loss price must be positive")
        if normalized_side == "buy" and stop_loss_price >= entry_price:
            raise RiskRejected("long stop loss must be below entry price")
        if normalized_side == "sell" and stop_loss_price <= entry_price:
            raise RiskRejected("short stop loss must be above entry price")

    if account_equity is None:
        return
    if not math.isfinite(account_equity) or account_equity <= 0:
        raise RiskRejected("account equity must be positive")
    if entry_price is None or stop_loss_price is None or quantity is None:
        raise RiskRejected("entry, stop loss and quantity are required for risk-per-trade validation")
    if not all(math.isfinite(value) for value in (entry_price, stop_loss_price, quantity)) or entry_price <= 0 or stop_loss_price <= 0 or quantity <= 0:
        raise RiskRejected("entry, stop loss and quantity must be positive")

    risk_amount = abs(entry_price - stop_loss_price) * quantity
    risk_budget = account_equity * (limits.risk_per_trade_pct / 100)
    if risk_amount > risk_budget:
        raise RiskRejected("order exceeds risk-per-trade budget")
