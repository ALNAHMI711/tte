from fastapi.testclient import TestClient

from trading.api import create_app
from trading.auth import AuthenticationService, credential_from_password
from trading.session import SessionStore

PASSWORD = "correct horse battery staple"


def test_chart_page_requires_authentication():
    auth = AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        SessionStore(ttl_seconds=100, step_up_seconds=10),
    )
    client = TestClient(create_app(auth), base_url="https://testserver")
    response = client.get("/chart.html")
    assert response.status_code == 401
    assert response.json()["error"] == "authentication_required"


def test_chart_page_is_served_after_authentication():
    auth = AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        SessionStore(ttl_seconds=100, step_up_seconds=10),
    )
    client = TestClient(create_app(auth), base_url="https://testserver")
    login = client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    assert login.status_code == 200
    response = client.get("/chart.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Binance Spot Testnet" in response.text
