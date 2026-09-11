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


def test_login_sets_secure_httponly_session_cookie():
    client = make_client()
    response = client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "tte_session=" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_session_endpoint_requires_authentication():
    client = make_client()
    assert client.get("/control/session").status_code == 401
    client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    response = client.get("/control/session")
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_state_changing_routes_require_csrf():
    client = make_client()
    client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    assert client.post("/logout").status_code == 403
    assert client.post("/control/step-up", json={"password": PASSWORD}).status_code == 403


def test_step_up_uses_session_identity_and_csrf_double_submit():
    client = make_client()
    client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    csrf = client.get("/csrf").json()["csrf_token"]
    response = client.post(
        "/control/step-up",
        json={"user_id": "attacker", "password": PASSWORD},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 200
    status = client.get("/control/session")
    assert status.json()["user_id"] == "admin"
    assert status.json()["step_up"] is True


def test_invalid_login_does_not_leak_credential_details():
    client = make_client()
    response = client.post("/login", json={"user_id": "admin", "password": "wrong password"})
    assert response.status_code == 401
    assert response.json() == {"error": "authentication_failed"}
