from fastapi.testclient import TestClient

from trading.api import create_app
from trading.audit_store import SQLiteAuditStore
from trading.auth import AuthenticationService, credential_from_password
from trading.server_ip import PublicIPClient, PublicIPResult, PublicIPError
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


def test_server_ip_endpoint_requires_authentication():
    client = make_client()
    assert client.get("/control/server-ip").status_code == 401


def test_server_ip_endpoint_returns_safe_readiness_result():
    auth = AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        SessionStore(ttl_seconds=100, step_up_seconds=10),
    )
    client = TestClient(
        create_app(
            auth,
            public_ip_client=PublicIPClient(url="https://example.test/ip"),
        ),
        base_url="https://testserver",
    )
    client.app.state.public_ip_client.resolve = lambda: PublicIPResult(  # type: ignore[method-assign]
        ip="203.0.113.10", source="https://example.test/ip"
    )
    assert client.post("/login", json={"user_id": "admin", "password": PASSWORD}).status_code == 200
    response = client.get("/control/server-ip")
    assert response.status_code == 200
    assert response.json() == {
        "ip": "203.0.113.10",
        "source": "https://example.test/ip",
        "trusted_ip_ready": True,
    }


def test_server_ip_endpoint_fails_closed_when_lookup_fails():
    auth = AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        SessionStore(ttl_seconds=100, step_up_seconds=10),
    )
    client = TestClient(
        create_app(auth, public_ip_client=PublicIPClient(url="https://example.test/ip")),
        base_url="https://testserver",
    )
    client.app.state.public_ip_client.resolve = lambda: (_ for _ in ()).throw(  # type: ignore[method-assign]
        PublicIPError("lookup failed")
    )
    client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    response = client.get("/control/server-ip")
    assert response.status_code == 503
    assert response.json() == {"error": "server_ip_unavailable"}


def test_kill_switch_audit_persists_and_chain_verifies(tmp_path):
    auth = AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        SessionStore(ttl_seconds=100, step_up_seconds=10),
    )
    with SQLiteAuditStore(tmp_path / "audit.sqlite3") as store:
        client = TestClient(
            create_app(auth, audit_store=store),
            base_url="https://testserver",
        )
        assert client.post("/login", json={"user_id": "admin", "password": PASSWORD}).status_code == 200
        csrf = client.get("/csrf").json()["csrf_token"]
        assert client.post(
            "/control/step-up",
            json={"user_id": "admin", "password": PASSWORD},
            headers={"x-csrf-token": csrf},
        ).status_code == 200
        response = client.post(
            "/control/kill-switch",
            json={"enabled": True, "reason": "integration test"},
            headers={"x-csrf-token": csrf, "x-request-id": "audit-integration-1"},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is True

        events = store.list(limit=10)
        kill_events = [event for event in events if event.action == "kill_switch"]
        assert len(kill_events) == 1
        event = kill_events[0]
        assert event.actor == "admin"
        assert event.outcome == "success"
        assert event.request_id == "audit-integration-1"
        assert dict(event.details) == {"enabled": "True", "reason_present": "True"}
        assert "integration test" not in str(event.details)
        assert store.verify_chain() is True
