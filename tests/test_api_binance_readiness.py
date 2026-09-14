from fastapi.testclient import TestClient

from trading.api import create_app
from trading.auth import AuthenticationService, credential_from_password
from trading.binance_connectivity import BinanceConnectivityResult
from trading.binance_readiness import BinanceReadinessStatus
from trading.binance_preflight import BinancePreflightReport, PreflightCheck, PreflightStatus
from trading.server_ip import PublicIPResult
from trading.session import SessionStore


PASSWORD = "correct horse battery staple"


def make_auth():
    return AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        SessionStore(ttl_seconds=100, step_up_seconds=10),
    )


def make_status():
    preflight = BinancePreflightReport(
        passed=True,
        checks=(
            PreflightCheck("live_requested", PreflightStatus.PASS),
            PreflightCheck("api_key_configured", PreflightStatus.PASS),
        ),
    )
    connectivity = BinanceConnectivityResult(
        reachable=True,
        environment="testnet",
        checks=("environment=testnet", "public_api=reachable", "orders=not_supported"),
    )
    return BinanceReadinessStatus(
        preflight=preflight,
        connectivity=connectivity,
        server_ip=PublicIPResult(ip="203.0.113.10", source="https://example.test/ip"),
    )


def test_binance_readiness_endpoint_requires_authentication():
    client = TestClient(create_app(make_auth()), base_url="https://testserver")
    assert client.get("/control/binance-readiness").status_code == 401


def test_binance_readiness_endpoint_returns_safe_snapshot():
    client = TestClient(
        create_app(make_auth(), binance_readiness=make_status()),
        base_url="https://testserver",
    )
    assert client.post("/login", json={"user_id": "admin", "password": PASSWORD}).status_code == 200

    response = client.get("/control/binance-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["live_enabled"] is False
    assert payload["connectivity"]["environment"] == "testnet"
    assert payload["connectivity"]["checks"][-1] == "orders=not_supported"
    assert payload["server_ip"] == {
        "ip": "203.0.113.10",
        "source": "https://example.test/ip",
    }


def test_binance_readiness_endpoint_fails_closed_when_unconfigured():
    client = TestClient(create_app(make_auth()), base_url="https://testserver")
    assert client.post("/login", json={"user_id": "admin", "password": PASSWORD}).status_code == 200

    response = client.get("/control/binance-readiness")

    assert response.status_code == 503
    assert response.json() == {"error": "binance_readiness_unavailable"}
