from fastapi.testclient import TestClient

from trading.api import create_app
from trading.audit import AuditLog
from trading.auth import AuthenticationService, credential_from_password
from trading.kill_switch import KillSwitch
from trading.session import SessionStore


PASSWORD = "correct horse battery staple"


def make_client(kill_switch: KillSwitch | None = None, audit_log: AuditLog | None = None, *, sessions: SessionStore | None = None):
    auth = AuthenticationService(
        {"admin": credential_from_password("admin", PASSWORD)},
        sessions or SessionStore(ttl_seconds=100, step_up_seconds=10),
    )
    return TestClient(
        create_app(auth, kill_switch=kill_switch, audit_log=audit_log),
        base_url="https://testserver",
    )


def login_and_csrf(client: TestClient) -> str:
    login = client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    assert login.status_code == 200
    csrf = client.get("/csrf")
    assert csrf.status_code == 200
    return csrf.json()["csrf_token"]


def step_up(client: TestClient, csrf_token: str):
    return client.post(
        "/control/step-up",
        json={"user_id": "admin", "password": PASSWORD},
        headers={"x-csrf-token": csrf_token},
    )


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


def test_dashboard_status_exposes_shared_kill_switch_state():
    kill_switch = KillSwitch()
    kill_switch.activate("operator requested stop")
    client = make_client(kill_switch)

    login = client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    assert login.status_code == 200

    response = client.get("/dashboard/status")
    assert response.status_code == 200
    data = response.json()
    assert data["kill_switch"] is True
    assert data["kill_switch_reason"] == "operator requested stop"


def test_kill_switch_control_requires_authentication():
    client = make_client()
    response = client.post("/control/kill-switch", json={"enabled": True, "reason": "stop"})
    assert response.status_code == 401


def test_kill_switch_control_requires_csrf():
    client = make_client()
    login = client.post("/login", json={"user_id": "admin", "password": PASSWORD})
    assert login.status_code == 200
    response = client.post("/control/kill-switch", json={"enabled": True, "reason": "stop"})
    assert response.status_code == 403
    assert response.json()["error"] == "csrf_failed"


def test_kill_switch_control_requires_step_up():
    client = make_client()
    csrf_token = login_and_csrf(client)
    response = client.post(
        "/control/kill-switch",
        json={"enabled": True, "reason": "operator requested stop"},
        headers={"x-csrf-token": csrf_token},
    )
    assert response.status_code == 403
    assert response.json()["error"] == "step_up_required"


def test_kill_switch_control_activates_and_deactivates_after_step_up():
    kill_switch = KillSwitch()
    client = make_client(kill_switch)
    csrf_token = login_and_csrf(client)

    elevated = step_up(client, csrf_token)
    assert elevated.status_code == 200
    assert elevated.json() == {"elevated": True}

    activate = client.post(
        "/control/kill-switch",
        json={"enabled": True, "reason": "operator requested stop"},
        headers={"x-csrf-token": csrf_token},
    )
    assert activate.status_code == 200
    assert activate.json() == {"enabled": True, "reason": "operator requested stop"}
    assert kill_switch.blocks_new_orders() is True

    deactivate = client.post(
        "/control/kill-switch",
        json={"enabled": False, "reason": "ignored on deactivate"},
        headers={"x-csrf-token": csrf_token},
    )
    assert deactivate.status_code == 200
    assert deactivate.json() == {"enabled": False, "reason": ""}
    assert kill_switch.blocks_new_orders() is False


def test_kill_switch_control_rejects_invalid_payload_without_mutating_state():
    kill_switch = KillSwitch()
    client = make_client(kill_switch)
    csrf_token = login_and_csrf(client)
    assert step_up(client, csrf_token).status_code == 200

    response = client.post(
        "/control/kill-switch",
        json={"enabled": "yes", "reason": "operator requested stop"},
        headers={"x-csrf-token": csrf_token},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"
    assert kill_switch.blocks_new_orders() is False


def test_kill_switch_control_records_safe_audit_events():
    audit_log = AuditLog()
    client = make_client(audit_log=audit_log)
    csrf_token = login_and_csrf(client)
    assert step_up(client, csrf_token).status_code == 200

    headers = {"x-csrf-token": csrf_token, "x-request-id": "req-kill-1"}
    activate = client.post(
        "/control/kill-switch",
        json={"enabled": True, "reason": "sensitive operator note"},
        headers=headers,
    )
    assert activate.status_code == 200

    headers["x-request-id"] = "req-kill-2"
    deactivate = client.post(
        "/control/kill-switch",
        json={"enabled": False, "reason": "another sensitive note"},
        headers=headers,
    )
    assert deactivate.status_code == 200

    events = audit_log.snapshot()
    assert len(events) == 2
    assert [event.action for event in events] == ["kill_switch", "kill_switch"]
    assert [event.actor for event in events] == ["admin", "admin"]
    assert [event.outcome for event in events] == ["success", "success"]
    assert [event.request_id for event in events] == ["req-kill-1", "req-kill-2"]
    assert [dict(event.details) for event in events] == [
        {"enabled": True, "reason_present": True},
        {"enabled": False, "reason_present": True},
    ]
    assert all("sensitive" not in str(event.to_dict()).lower() for event in events)


def test_kill_switch_control_denies_expired_step_up(monkeypatch):
    import trading.session as session_module

    sessions = SessionStore(ttl_seconds=100, step_up_seconds=10)
    client = make_client(sessions=sessions)
    csrf_token = login_and_csrf(client)
    assert step_up(client, csrf_token).status_code == 200

    now = session_module.time.time()
    monkeypatch.setattr(session_module.time, "time", lambda: now + 11)
    response = client.post(
        "/control/kill-switch",
        json={"enabled": True, "reason": "expired elevation"},
        headers={"x-csrf-token": csrf_token},
    )
    assert response.status_code == 403
    assert response.json()["error"] == "step_up_required"


def test_kill_switch_step_up_is_isolated_per_session():
    client_a = make_client()
    client_b = make_client()
    csrf_a = login_and_csrf(client_a)
    csrf_b = login_and_csrf(client_b)

    assert step_up(client_a, csrf_a).status_code == 200

    response_a = client_a.post(
        "/control/kill-switch",
        json={"enabled": True, "reason": "session a"},
        headers={"x-csrf-token": csrf_a},
    )
    assert response_a.status_code == 200

    response_b = client_b.post(
        "/control/kill-switch",
        json={"enabled": False, "reason": "session b"},
        headers={"x-csrf-token": csrf_b},
    )
    assert response_b.status_code == 403
    assert response_b.json()["error"] == "step_up_required"
