"""Explicit runtime factories for authentication and session persistence."""
from __future__ import annotations

from collections.abc import Mapping

from .auth import AuthenticationService, UserCredential
from .config import Settings, settings as default_settings
from .session import SessionStore
from .session_store import SQLiteSessionStore


def create_session_store(config: Settings = default_settings) -> SessionStore:
    """Build the configured store; production configuration fails closed."""
    config.validate()
    if config.session_store_backend == "sqlite":
        return SQLiteSessionStore(
            config.session_store_path,
            ttl_seconds=config.session_ttl_seconds,
            step_up_seconds=config.session_step_up_seconds,
            secret=config.session_secret,
        )
    if config.app_env.strip().lower() in {"production", "prod"}:
        raise ValueError("in-memory sessions are not permitted in production")
    return SessionStore(
        ttl_seconds=config.session_ttl_seconds,
        step_up_seconds=config.session_step_up_seconds,
    )


def create_authentication_service(
    credentials: Mapping[str, UserCredential],
    config: Settings = default_settings,
) -> AuthenticationService:
    """Create auth with the configured session backend and supplied credentials.

    Credential loading remains the responsibility of the deployment's secret or
    identity provider; this factory never invents a default administrator.
    """
    return AuthenticationService(dict(credentials), sessions=create_session_store(config))
