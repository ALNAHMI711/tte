"""Runtime configuration with safe defaults: paper trading only."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    live_trading: bool = _bool("LIVE_TRADING", False)
    paper_trading: bool = _bool("PAPER_TRADING", True)
    admin_auth_required: bool = _bool("ADMIN_AUTH_REQUIRED", True)
    session_secret: str = os.getenv("SESSION_SECRET", "")

    def validate(self) -> None:
        if self.live_trading and not self.session_secret:
            raise ValueError("LIVE_TRADING requires a configured SESSION_SECRET")
        if self.live_trading and self.paper_trading:
            raise ValueError("LIVE_TRADING and PAPER_TRADING cannot both be enabled")


settings = Settings()
settings.validate()
