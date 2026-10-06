"""Runtime strategy contract: signals only, never exchange execution."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Sequence


class StrategyAction(str, Enum):
    HOLD = "hold"
    ENTER_LONG = "enter_long"
    EXIT_LONG = "exit_long"


@dataclass(frozen=True)
class StrategyCandle:
    time: int | float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    candles: tuple[StrategyCandle, ...]
    has_long_position: bool = False


class RuntimeStrategy(Protocol):
    name: str

    def evaluate(self, context: StrategyContext) -> StrategyAction: ...


class EmaCrossStrategy:
    """Deterministic EMA cross signal source; it cannot place orders."""

    name = "EMA 20/50 Cross"

    def __init__(self, fast: int = 20, slow: int = 50) -> None:
        if fast < 1 or slow <= fast:
            raise ValueError("slow period must be greater than fast period")
        self.fast = fast
        self.slow = slow

    @staticmethod
    def _ema(values: Sequence[float], period: int) -> list[float | None]:
        result: list[float | None] = [None] * len(values)
        if len(values) < period:
            return result
        previous = sum(values[:period]) / period
        result[period - 1] = previous
        alpha = 2 / (period + 1)
        for i in range(period, len(values)):
            previous = (values[i] - previous) * alpha + previous
            result[i] = previous
        return result

    def evaluate(self, context: StrategyContext) -> StrategyAction:
        if not context.candles:
            return StrategyAction.HOLD
        closes = [c.close for c in context.candles]
        fast = self._ema(closes, self.fast)
        slow = self._ema(closes, self.slow)
        i = len(closes) - 1
        if i < 1 or fast[i] is None or slow[i] is None:
            return StrategyAction.HOLD
        previous_fast, previous_slow = fast[i - 1], slow[i - 1]
        if not context.has_long_position and fast[i] > slow[i] and (
            previous_fast is None or previous_slow is None or previous_fast <= previous_slow
        ):
            return StrategyAction.ENTER_LONG
        if context.has_long_position and fast[i] < slow[i]:
            return StrategyAction.EXIT_LONG
        return StrategyAction.HOLD
