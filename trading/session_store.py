"""SQLite-backed session store shared across application worker processes."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .security_core import new_session_token
from .session import Session, SessionStore


class SQLiteSessionStore(SessionStore):
    """Persist only keyed session-token digests, never raw browser tokens.

    Suitable for a single-host deployment with a local durable SQLite volume.
    Use PostgreSQL/Redis-backed storage for multi-host deployments.
    """

    def __init__(
        self,
        database_path: str | Path,
        ttl_seconds: int = 3600,
        step_up_seconds: int = 300,
    ) -> None:
        if ttl_seconds <= 0 or step_up_seconds <= 0:
            raise ValueError("session TTLs must be positive")
        self.ttl_seconds = ttl_seconds
        self.step_up_seconds = step_up_seconds
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token_digest TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    step_up_until REAL NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        if self.database_path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def create(self, user_id: str, now: float | None = None) -> Session:
        if not user_id:
            raise ValueError("user_id is required")
        current = time.time() if now is None else now
        token = new_session_token()
        session = Session(token, user_id, current, current + self.ttl_seconds)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(token_digest, user_id, created_at, expires_at, step_up_until)
                VALUES (?, ?, ?, ?, ?)
                """,
                (self._digest(token), user_id, session.created_at, session.expires_at, 0.0),
            )
        return session

    def get(self, token: str, now: float | None = None) -> Session | None:
        if not token:
            return None
        current = time.time() if now is None else now
        digest = self._digest(token)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id, created_at, expires_at, step_up_until FROM sessions WHERE token_digest = ?",
                (digest,),
            ).fetchone()
            if row is None:
                return None
            if current >= row[2]:
                connection.execute("DELETE FROM sessions WHERE token_digest = ?", (digest,))
                return None
        return Session(token, row[0], row[1], row[2], row[3])

    def elevate(self, token: str, now: float | None = None) -> Session | None:
        if not token:
            return None
        current = time.time() if now is None else now
        digest = self._digest(token)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT user_id, created_at, expires_at FROM sessions WHERE token_digest = ?",
                (digest,),
            ).fetchone()
            if row is None or current >= row[2]:
                connection.execute("DELETE FROM sessions WHERE token_digest = ?", (digest,))
                return None
            step_up_until = min(row[2], current + self.step_up_seconds)
            connection.execute(
                "UPDATE sessions SET step_up_until = ? WHERE token_digest = ?",
                (step_up_until, digest),
            )
        return Session(token, row[0], row[1], row[2], step_up_until)

    def revoke(self, token: str) -> bool:
        if not token:
            return False
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE token_digest = ?",
                (self._digest(token),),
            )
            return cursor.rowcount > 0
