from trading.session_store import SQLiteSessionStore


def test_sqlite_sessions_are_shared_between_store_instances(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    first_worker = SQLiteSessionStore(database, ttl_seconds=100, step_up_seconds=10)
    second_worker = SQLiteSessionStore(database, ttl_seconds=100, step_up_seconds=10)

    session = first_worker.create("admin", now=1000)
    assert second_worker.get(session.token, now=1001) == session

    elevated = second_worker.elevate(session.token, now=1002)
    assert elevated is not None
    assert elevated.step_up_active(now=1005)
    assert first_worker.get(session.token, now=1005) == elevated

    assert second_worker.revoke(session.token)
    assert first_worker.get(session.token, now=1006) is None


def test_sqlite_session_expiry_is_enforced_across_workers(tmp_path):
    database = tmp_path / "sessions.sqlite3"
    first_worker = SQLiteSessionStore(database, ttl_seconds=10)
    second_worker = SQLiteSessionStore(database, ttl_seconds=10)

    session = first_worker.create("admin", now=100)
    assert second_worker.get(session.token, now=109) is not None
    assert second_worker.get(session.token, now=110) is None
    assert first_worker.get(session.token, now=110) is None
