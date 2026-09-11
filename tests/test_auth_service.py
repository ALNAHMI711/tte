from trading.auth import AuthenticationService, credential_from_password
from trading.session import SessionStore


def make_service():
    credential = credential_from_password("admin", "correct horse battery staple")
    return AuthenticationService({"admin": credential}, SessionStore(ttl_seconds=100, step_up_seconds=10))


def test_success_creates_session_without_returning_password():
    service = make_service()
    result = service.authenticate("admin", "correct horse battery staple", request_id="r1", now=100.0)
    assert result.authenticated
    assert result.session is not None
    assert service.sessions.get(result.session.token, now=101.0) is not None
    assert "password" not in str(result.audit_event).lower()


def test_bad_credentials_are_throttled():
    service = make_service()
    for _ in range(5):
        result = service.authenticate("admin", "wrong password", now=100.0)
        assert not result.authenticated
    blocked = service.authenticate("admin", "correct horse battery staple", now=101.0)
    assert not blocked.authenticated
    assert blocked.audit_event is not None
    assert blocked.audit_event.outcome == "blocked"


def test_step_up_elevates_existing_session_temporarily():
    service = make_service()
    login = service.authenticate("admin", "correct horse battery staple", now=100.0)
    assert login.session is not None
    elevated = service.step_up(login.session.token, "correct horse battery staple", now=101.0)
    assert elevated.authenticated
    assert elevated.session is not None
    assert elevated.session.step_up_active(now=105.0)
    assert not elevated.session.step_up_active(now=112.0)


def test_invalid_step_up_does_not_elevate():
    service = make_service()
    login = service.authenticate("admin", "correct horse battery staple", now=100.0)
    assert login.session is not None
    result = service.step_up(login.session.token, "wrong password", now=101.0)
    assert not result.authenticated
    assert not login.session.step_up_active(now=101.0)


def test_logout_revokes_session():
    service = make_service()
    login = service.authenticate("admin", "correct horse battery staple", now=100.0)
    assert login.session is not None
    assert service.logout(login.session.token)
    assert service.sessions.get(login.session.token, now=101.0) is None
