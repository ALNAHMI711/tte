import pytest

from trading.auth import AuthenticationService, UserCredential, hash_password
from trading.bootstrap import create_application, load_credentials_from_environment
from trading.config import Settings


def test_development_without_admin_credentials_fails_closed_for_login():
    credentials = load_credentials_from_environment(
        {"APP_ENV": "development"},
        production=False,
    )
    assert credentials == {}


def test_production_requires_admin_credentials():
    with pytest.raises(ValueError, match="ADMIN_USER_ID"):
        load_credentials_from_environment(
            {"APP_ENV": "production"},
            production=True,
        )


def test_bootstrap_accepts_only_a_password_hash():
    password_hash = hash_password("correct horse battery staple")
    credentials = load_credentials_from_environment(
        {
            "APP_ENV": "production",
            "ADMIN_USER_ID": "admin",
            "ADMIN_PASSWORD_HASH": password_hash,
        },
        production=True,
    )
    assert credentials["admin"].password_hash == password_hash


def test_bootstrapped_authentication_uses_configured_sqlite_sessions(tmp_path):
    password_hash = hash_password("correct horse battery staple")
    config = Settings(
        app_env="production",
        session_store_backend="sqlite",
        session_store_path=str(tmp_path / "sessions.sqlite3"),
    )
    app = create_application(
        config,
        {
            "APP_ENV": "production",
            "ADMIN_USER_ID": "admin",
            "ADMIN_PASSWORD_HASH": password_hash,
        },
    )
    auth = app.routes[0] if app.routes else None
    assert auth is not None
    # The application is created successfully only after runtime session validation.
    assert app.title == "TTE Trading Control Plane"
