from datetime import datetime, timezone

from fastapi.testclient import TestClient

from trading.api import create_app
from trading.auth import AuthenticationService, credential_from_password
from trading.market import Candle
from trading.session import SessionStore


PASSWORD = "correct horse battery staple"


class FakeMarketClient:
    def candles(self, symbol: str, timeframe: str, limit: int):
        return (
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=12.0,
            ),
        )


def client():
    auth = AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        SessionStore(ttl_seconds=100, step_up_seconds=10),
    )
    return TestClient(
        create_app(auth, market_client=FakeMarketClient()),
        base_url="https://testserver",
    )


def test_market_candles_requires_authentication():
    response = client().get("/market/candles")
    assert response.status_code == 401
    assert response.json()["error"] == "authentication_required"


def test_market_candles_returns_normalized_read_only_data():
    c = client()
    login = c.post("/login", json={"user_id": "admin", "password": PASSWORD})
    assert login.status_code == 200

    response = c.get("/market/candles?symbol=btcusdt&timeframe=1m&limit=1")
    assert response.status_code == 200
    assert response.json() == {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "environment": "TESTNET",
        "candles": [{
            "time": 1767225600,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 12.0,
        }],
    }


def test_market_candles_rejects_invalid_limit():
    c = client()
    assert c.post("/login", json={"user_id": "admin", "password": PASSWORD}).status_code == 200
    response = c.get("/market/candles?limit=1001")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_market_request"
