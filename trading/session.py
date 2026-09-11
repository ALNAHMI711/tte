"""Minimal secure in-memory session and login throttling primitives."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import time

from .security_core import new_session_token


@dataclass(frozen=True)
class Session:
    token: str
    user_id: str
    created_at: float
    expires_at: float
    step_up_until: float = 0.0

    def active(self, now: float | None = None) -> bool:
        return (time.time() if now is None else now) < self.expires_at

    def step_up_active(self, now: float | None = None) -> bool:
        return self.active(now) and (time.time() if now is None else now) < self.step_up_until


class SessionStore:
    """Process-local session store; production deployments should use a shared store."""

    def __init__(self, ttl_seconds: int = 3600, step_up_seconds: int = 300) -> None:
        if ttl_seconds <= 0 or step_up_seconds <= 0:
            raise ValueError("session TTLs must be positive")
        self.ttl_seconds = ttl_seconds
        self.step_up_seconds = step_up_seconds
        self._sessions: dict[str, Session] = {}

    def create(self, user_id: str, now: float | None = None) -> Session:
        if not user_id:
            raise ValueError("user_id is required")
        current = time.time() if now is None else now
        token = new_session_token()
        session = Session(token, user_id, current, current + self.ttl_seconds)
        self._sessions[self._digest(token)] = session
        return session

    def get(self, token: str, now: float | None = None) -> Session | None:
        if not token:
            return None
        digest = self._digest(token)
        session = self._sessions.get(digest)
        if session is None or not session.active(now):
            if session is not None:
                self._sessions.pop(digest, None)
            return None
        return session

    def elevate(self, token: str, now: float | None = None) -> Session | None:
        session = self.get(token, now)
        if session is None:
            return None
        current = time.time() if now is None else now
        elevated = Session(
            session.token,
            session.user_id,
            session.created_at,
            session.expires_at,
            min(session.expires_at, current + self.step_up_seconds),
        )
        self._sessions[self._digest(token)] = elevated
        return elevated

    def revoke(self, token: str) -> bool:
        """Revoke by token without requiring the session to still be unexpired."""
        if not token:
            return False
        return self._sessions.pop(self._digest(token), None) is not None

    @staticmethod
    def _digest(token: str) -> str:
        return hmac.new(b"tte-session-index", token.encode(), hashlib.sha256).hexdigest()


@dataclass
class LoginThrottle:
    """Bounded exponential backoff after failed authentication attempts."""
    max_failures: int = 5
    base_delay: float = 1.0
    lock_seconds: float = 300.0
    failures: int = 0
    blocked_until: float = 0.0

    def allowed(self, now: float | None = None) -> bool:
        return (time.time() if now is None else now) >= self.blocked_until

    def failure(self, now: float | None = None) -> None:
        current = time.time() if now is None else now
        self.failures += 1
        if self.failures >= self.max_failures:
            self.blocked_until = current + self.lock_seconds
            return
        delay = self.base_delay * (2 ** (self.failures - 1))
        self.blocked_until = current + delay

    def success(self) -> None:
        self.failures = 0
        self.blocked_until = 0.0
