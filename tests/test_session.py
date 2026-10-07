import pytest
from trading.session import LoginThrottle, SessionStore


def test_session_lifecycle_and_step_up_are_time_bound():
    store = SessionStore(ttl_seconds=100, step_up_seconds=10)
    session = store.create("admin", now=1000)
    assert store.get(session.token, now=1099) is not None
    assert store.get(session.token, now=1100) is None

    session = store.create("admin", now=2000)
    assert not session.step_up_active(now=2001)
    elevated = store.elevate(session.token, now=2001)
    assert elevated is not None
    assert elevated.step_up_active(now=2010)
    assert not elevated.step_up_active(now=2011)
    assert store.revoke(session.token)
    assert store.get(session.token, now=2002) is None


def test_login_throttle_backs_off_and_resets():
    throttle = LoginThrottle(max_failures=3, base_delay=2, lock_seconds=30)
    assert throttle.allowed(now=100)
    throttle.failure(now=100)
    assert not throttle.allowed(now=101)
    assert throttle.allowed(now=102)
    throttle.failure(now=102)
    assert not throttle.allowed(now=105)
    throttle.failure(now=104)
    assert not throttle.allowed(now=133)
    assert throttle.allowed(now=134)
    throttle.success()
    assert throttle.failures == 0
    assert throttle.allowed(now=134)


def test_sqlite_session_survives_restart_and_never_persists_raw_token(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    secret = "test-session-secret"
    with SessionStore(ttl_seconds=100, step_up_seconds=10, path=path, secret=secret) as first:
        session = first.create("admin", now=1000)
        assert first.get(session.token, now=1001).user_id == "admin"
        assert session.token.encode() not in path.read_bytes()
        elevated = first.elevate(session.token, now=1002)
        assert elevated is not None

    with SessionStore(ttl_seconds=100, step_up_seconds=10, path=path, secret=secret) as second:
        restored = second.get(session.token, now=1003)
        assert restored is not None
        assert restored.user_id == "admin"
        assert restored.step_up_active(now=1003)
        assert second.revoke(session.token)
        assert second.get(session.token, now=1004) is None


def test_sqlite_session_rejects_wrong_secret(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    with SessionStore(path=path, secret="correct-secret") as first:
        session = first.create("admin", now=1000)
    with SessionStore(path=path, secret="wrong-secret") as second:
        assert second.get(session.token, now=1001) is None


def test_persistent_sessions_require_a_secret(tmp_path):
    with pytest.raises(ValueError, match="secret"):
        SessionStore(path=tmp_path / "sessions.sqlite3")
