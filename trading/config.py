"""Runtime configuration with safe defaults: paper trading only."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    live_trading: bool = _bool("LIVE_TRADING", False)
    paper_trading: bool = _bool("PAPER_TRADING", True)
    admin_auth_required: bool = _bool("ADMIN_AUTH_REQUIRED", True)
    session_secret: str = os.getenv("SESSION_SECRET", "")
    session_store_backend: str = os.getenv("SESSION_STORE_BACKEND", "memory").strip().lower()
    session_store_path: str = os.getenv("SESSION_STORE_PATH", "")
    session_ttl_seconds: int = _int("SESSION_TTL_SECONDS", 3600)
    session_step_up_seconds: int = _int("SESSION_STEP_UP_SECONDS", 300)

    def validate(self) -> None:
        if self.live_trading and not self.session_secret:
            raise ValueError("LIVE_TRADING requires a configured SESSION_SECRET")
        if self.live_trading and self.paper_trading:
            raise ValueError("LIVE_TRADING and PAPER_TRADING cannot both be enabled")
        if self.session_store_backend not in {"memory", "sqlite"}:
            raise ValueError("SESSION_STORE_BACKEND must be memory or sqlite")
        if self.session_ttl_seconds <= 0 or self.session_step_up_seconds <= 0:
            raise ValueError("session TTL settings must be positive")
        if self.session_store_backend == "sqlite" and not self.session_store_path:
            raise ValueError("SESSION_STORE_PATH is required when SESSION_STORE_BACKEND=sqlite")
        if self.app_env.strip().lower() in {"production", "prod"}:
            if self.session_store_backend != "sqlite":
                raise ValueError("production requires SESSION_STORE_BACKEND=sqlite")
            if not Path(self.session_store_path).is_absolute():
                raise ValueError("production SESSION_STORE_PATH must be an absolute path")


settings = Settings()
settings.validate()
