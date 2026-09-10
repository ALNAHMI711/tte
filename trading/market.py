"""Normalized market-data contracts; network adapters plug in later."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def validate(self) -> None:
        if min(self.open, self.high, self.low, self.close, self.volume) < 0:
            raise ValueError("market values cannot be negative")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("invalid OHLC relationship")


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    bids: tuple[tuple[float, float], ...]
    asks: tuple[tuple[float, float], ...]

    def validate(self) -> None:
        for price, size in (*self.bids, *self.asks):
            if price <= 0 or size < 0:
                raise ValueError("invalid order-book level")
