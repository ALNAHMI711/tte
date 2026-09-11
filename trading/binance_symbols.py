"""Binance Spot Testnet symbol metadata client with strict safety boundaries."""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .adapters import SymbolInfo
from .binance_market import TESTNET_BASE_URL


class BinanceSymbolError(RuntimeError):
    """Base error for normalized Binance symbol metadata failures."""


class BinanceSymbolNetworkError(BinanceSymbolError):
    """Raised for network or transport failures."""


class BinanceSymbolResponseError(BinanceSymbolError):
    """Raised for malformed exchange metadata."""


@dataclass(frozen=True)
class BinanceSymbolClient:
    """Read-only Spot Testnet exchange-info client."""

    base_url: str = TESTNET_BASE_URL
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.base_url.rstrip("/") != TESTNET_BASE_URL:
            raise BinanceSymbolError("only Binance Spot Testnet is permitted")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def _get(self, symbol: str | None = None) -> object:
        params = {"symbol": symbol.upper()} if symbol else {}
        query = urlencode(params)
        url = f"{self.base_url.rstrip('/')}/api/v3/exchangeInfo"
        if query:
            url = f"{url}?{query}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "tte-testnet/0.1"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise BinanceSymbolNetworkError("Binance Testnet exchange-info request failed") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BinanceSymbolResponseError("Binance Testnet returned invalid JSON") from exc

    @staticmethod
    def _decimal(value: object, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise BinanceSymbolResponseError(f"invalid {field}") from exc
        if not result.is_finite() or result < 0:
            raise BinanceSymbolResponseError(f"invalid {field}")
        return result

    def symbol_info(self, symbol: str) -> SymbolInfo:
        normalized = symbol.upper().strip()
        if not normalized:
            raise ValueError("symbol is required")
        data = self._get(normalized)
        if not isinstance(data, dict) or not isinstance(data.get("symbols"), list):
            raise BinanceSymbolResponseError("exchange-info response is malformed")
        matches = [item for item in data["symbols"] if isinstance(item, dict) and item.get("symbol") == normalized]
        if len(matches) != 1:
            raise BinanceSymbolResponseError("symbol metadata is missing or ambiguous")
        item = matches[0]
        try:
            base_asset = item["baseAsset"]
            quote_asset = item["quoteAsset"]
            status = item["status"]
            filters = item["filters"]
            if not isinstance(base_asset, str) or not base_asset or not isinstance(quote_asset, str) or not quote_asset:
                raise TypeError
            if status != "TRADING":
                raise ValueError("symbol is not trading")
            if not isinstance(filters, list):
                raise TypeError
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc) == "symbol is not trading":
                raise BinanceSymbolResponseError(str(exc)) from exc
            raise BinanceSymbolResponseError("symbol metadata is malformed") from exc

        by_type = {f.get("filterType"): f for f in filters if isinstance(f, dict)}
        lot = by_type.get("LOT_SIZE")
        notional = by_type.get("MIN_NOTIONAL") or by_type.get("NOTIONAL")
        if not isinstance(lot, dict) or not isinstance(notional, dict):
            raise BinanceSymbolResponseError("required symbol filters are missing")
        min_qty = self._decimal(lot.get("minQty"), "minQty")
        step = self._decimal(lot.get("stepSize"), "stepSize")
        min_notional = self._decimal(notional.get("minNotional"), "minNotional")
        if min_qty <= 0 or step <= 0:
            raise BinanceSymbolResponseError("quantity filters must be positive")
        result = SymbolInfo(
            symbol=normalized,
            base_asset=base_asset,
            quote_asset=quote_asset,
            min_quantity=float(min_qty),
            quantity_step=float(step),
            min_notional=float(min_notional),
        )
        result.validate()
        return result
