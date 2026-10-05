"""Production-safe application bootstrap for ASGI servers."""
from __future__ import annotations

import os
from collections.abc import Mapping

from .api import create_app
from .auth import AuthenticationService, UserCredential
from .config import Settings, settings as default_settings
from .runtime import create_authentication_service


def load_credentials_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    production: bool | None = None,
) -> dict[str, UserCredential]:
    """Load only an Argon2 password hash; never accept/store a plaintext password."""
    source = environ or os.environ
    is_production = (
        production
        if production is not None
        else source.get("APP_ENV", "development").strip().lower() in {"production", "prod"}
    )
    user_id = source.get("ADMIN_USER_ID", "").strip()
    password_hash = source.get("ADMIN_PASSWORD_HASH", "").strip()

    if not user_id or not password_hash:
        if is_production:
            raise ValueError("production requires ADMIN_USER_ID and ADMIN_PASSWORD_HASH")
        return {}

    return {user_id: UserCredential(user_id=user_id, password_hash=password_hash)}


def create_application(
    config: Settings = default_settings,
    environ: Mapping[str, str] | None = None,
):
    """Build the FastAPI control plane from deployment configuration and secrets."""
    credentials = load_credentials_from_environment(environ)
    auth = create_authentication_service(credentials, config)
    return create_app(auth)


application = create_application()
