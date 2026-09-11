from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse
from urllib.error import URLError

import pytest

from trading.binance_account import (
    BinanceAccountClient,
    BinanceAccountError,
    BinanceAccountNetworkError,
    BinanceAccountResponseError,
)
from trading.binance_market import TESTNET_BASE_URL
from trading.adapters import WithdrawalPermissionError


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_account_snapshot_is_signed_and_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    secret = "test-secret"

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["api_key"] = request.headers.get("X-mbx-apikey")
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "accountType": "SPOT",
                "canTrade": True,
                "canWithdraw": False,
                "balances": [
                    {"asset": "BTC", "free": "1.25", "locked": "0.25"},
                    {"asset": "USDT", "free": "100", "locked": "2"},
                ],
            }
        )

    monkeypatch.setattr("trading.binance_account.urlopen", fake_urlopen)
    monkeypatch.setattr("trading.binance_account.time.time", lambda: 1700000000.123)

    client = BinanceAccountClient("api-key", secret, recv_window=5000)
    snapshot = client.account_snapshot()

    parsed = urlparse(captured["url"])
    params = parse_qs(parsed.query)
    signed_query = "timestamp=1700000000123&recvWindow=5000"
    expected = hmac.new(secret.encode(), signed_query.encode(), hashlib.sha256).hexdigest()

    assert parsed.scheme == "https"
    assert f"{parsed.scheme}://{parsed.netloc}" == TESTNET_BASE_URL
    assert params["timestamp"] == ["1700000000123"]
    assert params["recvWindow"] == ["5000"]
    assert params["signature"] == [expected]
    assert captured["api_key"] == "api-key"
    assert captured["timeout"] == 10.0
    assert snapshot.account_id == "SPOT"
    assert snapshot.can_trade is True
    assert snapshot.can_withdraw is False
    assert snapshot.balances == (("BTC", 1.5), ("USDT", 102.0))


def test_client_rejects_non_testnet_base_url() -> None:
    with pytest.raises(BinanceAccountError, match="only Binance Spot Testnet"):
        BinanceAccountClient("key", "secret", base_url="https://api.binance.com")


def test_network_errors_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout):
        raise URLError("offline")

    monkeypatch.setattr("trading.binance_account.urlopen", fake_urlopen)

    with pytest.raises(BinanceAccountNetworkError, match="account request failed"):
        BinanceAccountClient("key", "secret").account_snapshot()


def test_invalid_json_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadResponse(FakeResponse):
        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr("trading.binance_account.urlopen", lambda request, timeout: BadResponse(None))

    with pytest.raises(BinanceAccountResponseError, match="invalid JSON"):
        BinanceAccountClient("key", "secret").account_snapshot()


def test_malformed_account_response_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "trading.binance_account.urlopen",
        lambda request, timeout: FakeResponse({"accountType": "SPOT", "canTrade": True}),
    )

    with pytest.raises(BinanceAccountResponseError, match="account response is malformed"):
        BinanceAccountClient("key", "secret").account_snapshot()


def test_withdrawal_permission_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "trading.binance_account.urlopen",
        lambda request, timeout: FakeResponse(
            {
                "accountType": "SPOT",
                "canTrade": True,
                "canWithdraw": True,
                "balances": [],
            }
        ),
    )

    with pytest.raises(WithdrawalPermissionError, match="withdrawal permission"):
        BinanceAccountClient("key", "secret").account_snapshot()


def test_secret_is_not_present_in_normalized_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "SUPER-SECRET-VALUE"

    def fake_urlopen(request, timeout):
        raise URLError("transport failure")

    monkeypatch.setattr("trading.binance_account.urlopen", fake_urlopen)

    with pytest.raises(BinanceAccountNetworkError) as exc_info:
        BinanceAccountClient("key", secret).account_snapshot()

    assert secret not in str(exc_info.value)
