"""Read-only Binance Spot Testnet authentication primitives.

This module signs authenticated requests but intentionally exposes no order or
withdrawal operation. Secrets are never included in exceptions or result data.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode


class BinanceAuthError(ValueError):
    """Raised when authenticated-request inputs are unsafe or incomplete."""


def build_signed_query(
    params: dict[str, object],
    api_secret: str,
    *,
    timestamp_ms: int | None = None,
    recv_window: int = 5000,
) -> str:
    """Return a Binance HMAC-SHA256 signed query string."""
    if not api_secret:
        raise BinanceAuthError("API secret is required")
    if recv_window <= 0 or recv_window > 60000:
        raise BinanceAuthError("recv_window must be between 1 and 60000")
    payload = dict(params)
    payload.setdefault("timestamp", timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    payload.setdefault("recvWindow", recv_window)
    query = urlencode(payload)
    signature = hmac.new(api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{query}&signature={signature}"


def validate_api_key(api_key: str) -> None:
    """Reject obviously missing credentials without persisting or exposing them."""
    if not api_key or not api_key.strip():
        raise BinanceAuthError("API key is required")
