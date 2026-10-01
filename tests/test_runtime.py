import pytest

from trading.auth import UserCredential, hash_password
from trading.config import Settings
from trading.runtime import create_authentication_service, create_session_store
from trading.session import SessionStore
from trading.session_store import SQLiteSessionStore


def test_development_defaults_to_process_local_sessions():
    config = Settings()
    assert isinstance(create_session_store(config), SessionStore)
    assert not isinstance(create_session_store(config), SQLiteSessionStore)


def test_sqlite_backend_is_selected_from_settings(tmp_path):
    config = Settings(
        session_store_backend="sqlite",
        session_store_path=str(tmp_path / "sessions.sqlite3"),
    )
    store = create_session_store(config)
    assert isinstance(store, SQLiteSessionStore)


def test_production_rejects_memory_session_backend():
    config = Settings(app_env="production", session_store_backend="memory")
    with pytest.raises(ValueError, match="production requires"):
        create_session_store(config)


def test_production_requires_absolute_sqlite_path():
    config = Settings(
        app_env="production",
        session_store_backend="sqlite",
        session_store_path="data/sessions.sqlite3",
    )
    with pytest.raises(ValueError, match="absolute path"):
        create_session_store(config)


def test_authentication_factory_uses_persistent_store_across_instances(tmp_path):
    config = Settings(
        app_env="production",
        session_store_backend="sqlite",
        session_store_path=str(tmp_path / "sessions.sqlite3"),
    )
    credentials = {"admin": UserCredential("admin", hash_password("a sufficiently long password"))}
    first = create_authentication_service(credentials, config)
    second = create_authentication_service(credentials, config)

    result = first.authenticate("admin", "a sufficiently long password", now=1000)
    assert result.authenticated and result.session is not None
    assert second.sessions.get(result.session.token, now=1001) == result.session
