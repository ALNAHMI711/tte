"""Secure session store with memory and SQLite-backed persistence."""
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

    def __init__(self, ttl_seconds: int = 3600, step_up_seconds: int = 300, *, path: str | None = None, secret: str | bytes | None = None) -> None:
        if ttl_seconds <= 0 or step_up_seconds <= 0:
            raise ValueError("session TTLs must be positive")
        if path is not None and not secret:
            raise ValueError("a session secret is required for persistent sessions")
        self.ttl_seconds = ttl_seconds
        self.step_up_seconds = step_up_seconds
        self._secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self._secret = self._secret or b"tte-session-index"
        self._sessions: dict[str, Session] = {}
        self._connection = None
        if path is not None:
            import sqlite3
            from pathlib import Path
            db_path = Path(path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(db_path)
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token_digest TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    step_up_until REAL NOT NULL DEFAULT 0
                )
            """)
            self._connection.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)")
            self._connection.commit()

    def create(self, user_id: str, now: float | None = None) -> Session:
        if not user_id:
            raise ValueError("user_id is required")
        current = time.time() if now is None else now
        token = new_session_token()
        session = Session(token, user_id, current, current + self.ttl_seconds)
        digest = self._digest(token)
        if self._connection is None:
            self._sessions[digest] = session
        else:
            self._connection.execute(
                "INSERT INTO sessions(token_digest,user_id,created_at,expires_at,step_up_until) VALUES(?,?,?,?,?)",
                (digest, session.user_id, session.created_at, session.expires_at, session.step_up_until),
            )
            self._connection.commit()
        return session

    def get(self, token: str, now: float | None = None) -> Session | None:
        if not token:
            return None
        digest = self._digest(token)
        current = time.time() if now is None else now
        if self._connection is None:
            session = self._sessions.get(digest)
            if session is None or not session.active(current):
                if session is not None:
                    self._sessions.pop(digest, None)
                return None
            return session
        row = self._connection.execute(
            "SELECT user_id,created_at,expires_at,step_up_until FROM sessions WHERE token_digest=?",
            (digest,),
        ).fetchone()
        if row is None:
            return None
        user_id, created_at, expires_at, step_up_until = row
        if current >= float(expires_at):
            self._connection.execute("DELETE FROM sessions WHERE token_digest=?", (digest,))
            self._connection.commit()
            return None
        return Session(token, str(user_id), float(created_at), float(expires_at), float(step_up_until))

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
        digest = self._digest(token)
        if self._connection is None:
            self._sessions[digest] = elevated
        else:
            self._connection.execute("UPDATE sessions SET step_up_until=? WHERE token_digest=?", (elevated.step_up_until, digest))
            self._connection.commit()
        return elevated

    def revoke(self, token: str) -> bool:
        """Revoke by token without requiring the session to still be unexpired."""
        if not token:
            return False
        digest = self._digest(token)
        if self._connection is None:
            return self._sessions.pop(digest, None) is not None
        cursor = self._connection.execute("DELETE FROM sessions WHERE token_digest=?", (digest,))
        self._connection.commit()
        return cursor.rowcount == 1

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _digest(self, token: str) -> str:
        return hmac.new(self._secret, token.encode(), hashlib.sha256).hexdigest()


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
