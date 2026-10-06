"""Deterministic, read-only backtesting primitives; never routes exchange orders."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Sequence

from .indicators import ema


class Signal(str, Enum):
    HOLD = "hold"
    LONG = "long"
    FLAT = "flat"


@dataclass(frozen=True)
class BacktestCandle:
    time: int | float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class Strategy(Protocol):
    name: str

    def signal(self, candles: Sequence[BacktestCandle], index: int) -> Signal: ...


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 1000.0
    position_fraction: float = 1.0
    fee_rate: float = 0.001
    slippage_bps: float = 0.0

    def validate(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if not 0 < self.position_fraction <= 1:
            raise ValueError("position_fraction must be in (0, 1]")
        if self.fee_rate < 0 or self.slippage_bps < 0:
            raise ValueError("cost settings must be nonnegative")


@dataclass(frozen=True)
class BacktestTrade:
    entry_time: int | float
    exit_time: int | float
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    net_pnl: float


@dataclass(frozen=True)
class BacktestResult:
    initial_cash: float
    final_equity: float
    net_pnl: float
    return_pct: float
    trades: tuple[BacktestTrade, ...]
    max_drawdown_pct: float


class SmaCrossStrategy:
    name = "EMA 20/50 Cross"

    def __init__(self, fast: int = 20, slow: int = 50) -> None:
        if fast < 1 or slow <= fast:
            raise ValueError("slow period must be greater than fast period")
        self.fast = fast
        self.slow = slow

    def signal(self, candles: Sequence[BacktestCandle], index: int) -> Signal:
        if index < 1:
            return Signal.HOLD
        closes = [c.close for c in candles[: index + 1]]
        fast = ema(closes, self.fast)
        slow = ema(closes, self.slow)
        if fast[index] is None or slow[index] is None:
            return Signal.HOLD
        if fast[index] > slow[index] and (fast[index - 1] is None or fast[index - 1] <= slow[index - 1]):
            return Signal.LONG
        if fast[index] < slow[index]:
            return Signal.FLAT
        return Signal.HOLD


class BacktestEngine:
    """Bar-close simulator with explicit fees/slippage and no exchange side effects."""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()
        self.config.validate()

    def run(self, candles: Sequence[BacktestCandle], strategy: Strategy) -> BacktestResult:
        if not candles:
            raise ValueError("candles must not be empty")
        for candle in candles:
            if not all(isinstance(v, (int, float)) for v in (candle.open, candle.high, candle.low, candle.close, candle.volume)):
                raise ValueError("candle values must be numeric")
            if candle.close <= 0:
                raise ValueError("candle close must be positive")

        cash = self.config.initial_cash
        quantity = 0.0
        entry_price = 0.0
        entry_time: int | float = candles[0].time
        entry_fees = 0.0
        trades: list[BacktestTrade] = []
        peak = cash
        max_drawdown = 0.0

        for index, candle in enumerate(candles):
            signal = strategy.signal(candles, index)
            if signal is Signal.LONG and quantity == 0:
                execution_price = candle.close * (1 + self.config.slippage_bps / 10000)
                allocation = cash * self.config.position_fraction
                fee = allocation * self.config.fee_rate
                spend = allocation
                if spend + fee > cash:
                    spend = cash / (1 + self.config.fee_rate)
                    fee = spend * self.config.fee_rate
                quantity = spend / execution_price
                cash -= spend + fee
                entry_price = execution_price
                entry_time = candle.time
                entry_fees = fee
            elif signal is Signal.FLAT and quantity > 0:
                execution_price = candle.close * (1 - self.config.slippage_bps / 10000)
                proceeds = quantity * execution_price
                fee = proceeds * self.config.fee_rate
                cash += proceeds - fee
                gross = quantity * (execution_price - entry_price)
                total_fees = entry_fees + fee
                trades.append(BacktestTrade(entry_time, candle.time, entry_price, execution_price, quantity, gross, total_fees, gross - total_fees))
                quantity = 0.0
                entry_price = 0.0
                entry_fees = 0.0

            equity = cash + quantity * candle.close
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)

        if quantity > 0:
            candle = candles[-1]
            execution_price = candle.close * (1 - self.config.slippage_bps / 10000)
            proceeds = quantity * execution_price
            fee = proceeds * self.config.fee_rate
            cash += proceeds - fee
            gross = quantity * (execution_price - entry_price)
            total_fees = entry_fees + fee
            trades.append(BacktestTrade(entry_time, candle.time, entry_price, execution_price, quantity, gross, total_fees, gross - total_fees))
            quantity = 0.0

        final_equity = cash
        net_pnl = final_equity - self.config.initial_cash
        return_pct = net_pnl / self.config.initial_cash * 100
        return BacktestResult(self.config.initial_cash, final_equity, net_pnl, return_pct, tuple(trades), max_drawdown)
