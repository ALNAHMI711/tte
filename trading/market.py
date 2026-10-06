"""Normalized market-data contracts and a read-only Binance Spot Testnet adapter."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


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


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    status: str
    base_asset: str
    quote_asset: str


class BinanceMarketData:
    """Read-only Binance Spot Testnet market-data client.
    
    This adapter never signs requests and never sends trading endpoints.
    The opener is injectable so parsing can be tested without network access.
    """

    BASE_URL = "https://testnet.binance.vision"

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        timeout: float = 10.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        normalized = base_url.rstrip("/")
        if normalized != self.BASE_URL:
            raise ValueError("only the Binance Spot Testnet endpoint is allowed")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._base_url = normalized
        self._timeout = timeout
        self._opener = opener

    def _get(self, path: str, params: dict[str, object]) -> object:
        query = urlencode(params)
        request = Request(
            f"{self._base_url}{path}?{query}",
            headers={"Accept": "application/json", "User-Agent": "tte-market-data/1.0"},
            method="GET",
        )
        with self._opener(request, timeout=self._timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized or not normalized.isalnum():
            raise ValueError("symbol must contain only letters and digits")
        return normalized

    def exchange_info(self, symbol: str) -> SymbolInfo:
        normalized = self._symbol(symbol)
        payload = self._get("/api/v3/exchangeInfo", {"symbol": normalized})
        if not isinstance(payload, dict):
            raise ValueError("Binance returned an invalid exchange-info payload")
        symbols = payload.get("symbols")
        if not isinstance(symbols, list) or not symbols:
            raise ValueError("Binance returned no symbol information")
        item = symbols[0]
        if not isinstance(item, dict):
            raise ValueError("Binance returned invalid symbol information")
        return SymbolInfo(
            symbol=str(item.get("symbol", normalized)).upper(),
            status=str(item.get("status", "")),
            base_asset=str(item.get("baseAsset", "")).upper(),
            quote_asset=str(item.get("quoteAsset", "")).upper(),
        )

    def klines(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 100,
    ) -> tuple[Candle, ...]:
        normalized = self._symbol(symbol)
        timeframe = timeframe.strip()
        if not timeframe:
            raise ValueError("timeframe is required")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        payload = self._get(
            "/api/v3/klines",
            {"symbol": normalized, "interval": timeframe, "limit": limit},
        )
        if not isinstance(payload, list):
            raise ValueError("Binance returned an invalid klines payload")

        candles: list[Candle] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                raise ValueError("Binance returned an invalid kline")
            try:
                candle = Candle(
                    symbol=normalized,
                    timeframe=timeframe,
                    timestamp=datetime.fromtimestamp(float(row[0]) / 1000, tz=timezone.utc),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Binance returned non-numeric kline data") from exc
            candle.validate()
            candles.append(candle)
        return tuple(candles)

    def order_book(self, symbol: str, *, limit: int = 100) -> OrderBookSnapshot:
        normalized = self._symbol(symbol)
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        payload = self._get(
            "/api/v3/depth",
            {"symbol": normalized, "limit": limit},
        )
        if not isinstance(payload, dict):
            raise ValueError("Binance returned an invalid order-book payload")

        def levels(name: str) -> tuple[tuple[float, float], ...]:
            raw = payload.get(name)
            if not isinstance(raw, list):
                raise ValueError(f"Binance returned an invalid {name} payload")
            parsed: list[tuple[float, float]] = []
            for level in raw:
                if not isinstance(level, list) or len(level) < 2:
                    raise ValueError("Binance returned an invalid order-book level")
                try:
                    parsed.append((float(level[0]), float(level[1])))
                except (TypeError, ValueError) as exc:
                    raise ValueError("Binance returned non-numeric order-book data") from exc
            return tuple(parsed)

        snapshot = OrderBookSnapshot(
            symbol=normalized,
            bids=levels("bids"),
            asks=levels("asks"),
        )
        snapshot.validate()
        return snapshot
