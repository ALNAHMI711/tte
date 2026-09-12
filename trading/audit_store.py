"""Tamper-evident SQLite audit persistence for security-sensitive events."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from pathlib import Path
from threading import RLock

from .audit import AuditEvent


class AuditIntegrityError(RuntimeError):
    """Raised when the persisted audit chain is invalid or was modified."""


class SQLiteAuditStore:
    """Append-only, hash-chained audit store.

    SQLite is the development/first-deployment backend. The schema deliberately
    blocks UPDATE/DELETE at the database level; PostgreSQL can implement the
    same contract later without changing callers.
    """

    def __init__(self, database: str | Path = "audit.sqlite3") -> None:
        self.database = str(database)
        self._lock = RLock()
        self._conn = sqlite3.connect(self.database, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    request_id TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events
                BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events
                BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;
                """
            )
            self._conn.commit()

    @staticmethod
    def _details(event: AuditEvent) -> str:
        return json.dumps(dict(event.details), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _hash(cls, event: AuditEvent, previous_hash: str) -> str:
        payload = {
            "action": event.action,
            "actor": event.actor,
            "outcome": event.outcome,
            "timestamp": event.timestamp,
            "request_id": event.request_id,
            "details": dict(event.details),
            "previous_hash": previous_hash,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def append(self, event: AuditEvent) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = "" if row is None else str(row[0])
            event_hash = self._hash(event, previous_hash)
            cursor = self._conn.execute(
                """INSERT INTO audit_events
                   (action, actor, outcome, timestamp, request_id, details_json, previous_hash, event_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (event.action, event.actor, event.outcome, event.timestamp, event.request_id,
                 self._details(event), previous_hash, event_hash),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def record(self, event: AuditEvent) -> AuditEvent:
        """Persist an event using the same recorder contract as the in-memory log."""
        if not isinstance(event, AuditEvent):
            raise TypeError("event must be an AuditEvent")
        self.append(event)
        return event

    def list(self, limit: int = 100) -> list[AuditEvent]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with self._lock:
            rows = self._conn.execute(
                """SELECT action, actor, outcome, timestamp, request_id, details_json
                   FROM audit_events ORDER BY sequence DESC LIMIT ?""", (limit,)
            ).fetchall()
        return [
            AuditEvent(
                action=row["action"], actor=row["actor"], outcome=row["outcome"],
                timestamp=row["timestamp"], request_id=row["request_id"],
                details=tuple(sorted((str(k), str(v)) for k, v in json.loads(row["details_json"]).items())),
            )
            for row in rows
        ]

    def verify_chain(self) -> bool:
        with self._lock:
            rows = self._conn.execute(
                """SELECT sequence, action, actor, outcome, timestamp, request_id,
                          details_json, previous_hash, event_hash
                   FROM audit_events ORDER BY sequence ASC"""
            ).fetchall()
        previous_hash = ""
        expected_sequence = 1
        for row in rows:
            if int(row["sequence"]) != expected_sequence:
                raise AuditIntegrityError("audit sequence is not contiguous")
            details = json.loads(row["details_json"])
            if not isinstance(details, dict):
                raise AuditIntegrityError("audit details are invalid")
            event = AuditEvent(
                action=row["action"], actor=row["actor"], outcome=row["outcome"],
                timestamp=row["timestamp"], request_id=row["request_id"],
                details=tuple(sorted((str(k), str(v)) for k, v in details.items())),
            )
            if row["previous_hash"] != previous_hash:
                raise AuditIntegrityError("audit previous hash mismatch")
            expected_hash = self._hash(event, previous_hash)
            if not hmac.compare_digest(expected_hash, row["event_hash"]):
                raise AuditIntegrityError("audit event hash mismatch")
            previous_hash = row["event_hash"]
            expected_sequence += 1
        return True

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "SQLiteAuditStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
