"""Binance Spot Testnet market-data client with strict environment safety."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .adapters import TradingEnvironment
from .market import Candle, OrderBookSnapshot


TESTNET_BASE_URL = "https://testnet.binance.vision"
LIVE_BASE_URL = "https://api.binance.com"


class BinanceMarketError(RuntimeError):
    """Base error for normalized Binance market-data failures."""


class BinanceEnvironmentError(BinanceMarketError):
    """Raised when the client is configured for an unsafe environment."""


class BinanceNetworkError(BinanceMarketError):
    """Raised for network, timeout, or transport failures."""


class BinanceResponseError(BinanceMarketError):
    """Raised when Binance returns an invalid/unexpected response."""


@dataclass(frozen=True)
class BinanceMarketClient:
    """Read-only Spot Testnet client.

    This client deliberately exposes market data only. It cannot place orders,
    and it rejects the production Binance base URL at construction time.
    """

    base_url: str = TESTNET_BASE_URL
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.base_url.rstrip("/") != TESTNET_BASE_URL:
            raise BinanceEnvironmentError("only Binance Spot Testnet is permitted")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def environment(self) -> TradingEnvironment:
        return TradingEnvironment.TESTNET

    def _get(self, path: str, params: dict[str, object] | None = None) -> object:
        query = urlencode(params or {})
        url = f"{self.base_url.rstrip('/')}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "tte-testnet/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise BinanceNetworkError("Binance Testnet market-data request failed") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BinanceResponseError("Binance Testnet returned invalid JSON") from exc

    def ping(self) -> bool:
        self._get("/api/v3/ping")
        return True

    def ticker(self, symbol: str) -> tuple[float, float]:
        data = self._get("/api/v3/ticker/bookTicker", {"symbol": symbol.upper()})
        if not isinstance(data, dict):
            raise BinanceResponseError("ticker response is malformed")
        try:
            return float(data["bidPrice"]), float(data["askPrice"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BinanceResponseError("ticker response is malformed") from exc

    def order_book(self, symbol: str, limit: int = 20) -> OrderBookSnapshot:
        if not 1 <= limit <= 1000:
            raise ValueError("order-book limit must be between 1 and 1000")
        data = self._get("/api/v3/depth", {"symbol": symbol.upper(), "limit": limit})
        if not isinstance(data, dict):
            raise BinanceResponseError("order-book response is malformed")
        try:
            bids = tuple((float(p), float(q)) for p, q in data["bids"])
            asks = tuple((float(p), float(q)) for p, q in data["asks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BinanceResponseError("order-book response is malformed") from exc
        snapshot = OrderBookSnapshot(symbol=symbol.upper(), bids=bids, asks=asks)
        snapshot.validate()
        return snapshot

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> tuple[Candle, ...]:
        if not 1 <= limit <= 1000:
            raise ValueError("candle limit must be between 1 and 1000")
        data = self._get(
            "/api/v3/klines",
            {"symbol": symbol.upper(), "interval": timeframe, "limit": limit},
        )
        if not isinstance(data, list):
            raise BinanceResponseError("candles response is malformed")
        candles: list[Candle] = []
        try:
            for row in data:
                if not isinstance(row, list) or len(row) < 6:
                    raise ValueError
                candle = Candle(
                    symbol=symbol.upper(),
                    timeframe=timeframe,
                    timestamp=datetime.fromtimestamp(float(row[0]) / 1000, tz=timezone.utc),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
                candle.validate()
                candles.append(candle)
        except (TypeError, ValueError, OverflowError) as exc:
            raise BinanceResponseError("candles response is malformed") from exc
        return tuple(candles)
