"""Authenticated Binance Spot Testnet account client; read-only by design."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .adapters import (
    AccountSnapshot,
    AdapterError,
    TradingEnvironment,
    enforce_safe_account,
)
from .binance_market import TESTNET_BASE_URL


class BinanceAccountError(AdapterError):
    """Base class for normalized Binance account failures."""


class BinanceAccountNetworkError(BinanceAccountError):
    """Raised for network, timeout, or transport failures."""


class BinanceAccountResponseError(BinanceAccountError):
    """Raised when Binance returns an invalid or unexpected account response."""


@dataclass(frozen=True)
class BinanceAccountClient:
    """Read-only authenticated Spot Testnet client.

    The base URL is immutable at the safety boundary: production Binance is
    intentionally impossible to select here. This client has no order method.
    """

    api_key: str
    api_secret: str
    base_url: str = TESTNET_BASE_URL
    timeout_seconds: float = 10.0
    recv_window: int = 5000

    def __post_init__(self) -> None:
        if self.base_url.rstrip("/") != TESTNET_BASE_URL:
            raise BinanceAccountError("only Binance Spot Testnet is permitted")
        if not self.api_key or not self.api_secret:
            raise BinanceAccountError("Binance Testnet credentials are required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 1 <= self.recv_window <= 60000:
            raise ValueError("recv_window must be between 1 and 60000")

    @property
    def environment(self) -> TradingEnvironment:
        return TradingEnvironment.TESTNET

    def _signed_get(self, path: str) -> object:
        params = {
            "timestamp": int(time.time() * 1000),
            "recvWindow": self.recv_window,
        }
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        url = f"{self.base_url.rstrip('/')}{path}?{query}&signature={signature}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "tte-testnet/0.1",
                "X-MBX-APIKEY": self.api_key,
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise BinanceAccountNetworkError(
                "Binance Testnet account request failed"
            ) from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BinanceAccountResponseError(
                "Binance Testnet returned invalid JSON"
            ) from exc

    def account_snapshot(self) -> AccountSnapshot:
        data = self._signed_get("/api/v3/account")
        if not isinstance(data, dict):
            raise BinanceAccountResponseError("account response is malformed")
        try:
            account_id = str(data["accountType"])
            can_trade = data["canTrade"]
            can_withdraw = data["canWithdraw"]
            raw_balances = data["balances"]
            if not isinstance(can_trade, bool) or not isinstance(can_withdraw, bool):
                raise TypeError
            if not isinstance(raw_balances, list):
                raise TypeError
            balances = []
            for item in raw_balances:
                if not isinstance(item, dict):
                    raise TypeError
                asset = item["asset"]
                free = float(item["free"])
                locked = float(item["locked"])
                if not isinstance(asset, str) or not asset or free < 0 or locked < 0:
                    raise ValueError
                balances.append((asset, free + locked))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise BinanceAccountResponseError("account response is malformed") from exc

        snapshot = AccountSnapshot(
            account_id=account_id,
            environment=TradingEnvironment.TESTNET,
            can_trade=can_trade,
            can_withdraw=can_withdraw,
            balances=tuple(balances),
        )
        enforce_safe_account(snapshot)
        return snapshot
