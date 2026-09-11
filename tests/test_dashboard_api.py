from fastapi.testclient import TestClient

from trading.api import create_app
from trading.auth import AuthenticationService, credential_from_password
from trading.session import SessionStore


PASSWORD = "correct horse battery staple"


def make_client():
    auth = AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        SessionStore(ttl_seconds=100, step_up_seconds=10),
    )
    return TestClient(create_app(auth), base_url="https://testserver")


def test_dashboard_status_requires_authenticated_session():
    client = make_client()
    response = client.get("/dashboard/status")
    assert response.status_code == 401


def test_dashboard_status_is_safe_and_paper_first():
    client = make_client()
    login = client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    assert login.status_code == 200
    response = client.get("/dashboard/status")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "PAPER"
    assert data["live_trading"] is False
    assert data["kill_switch"] is False
    assert len(data["adapters"]) == 7
    assert data["risk"] == {"per_trade_pct": 0.5, "daily_loss_pct": 2.0, "max_open": 5, "min_score": 85}
    assert "password" not in str(data).lower()
    assert "api_key" not in str(data).lower()
