from __future__ import annotations

import sqlite3

import pytest

from trading.audit import AuditEvent
from trading.audit_store import AuditIntegrityError, SQLiteAuditStore


def event(action: str, request_id: str = "req-1") -> AuditEvent:
    return AuditEvent.create(
        action=action,
        actor="admin",
        outcome="success",
        request_id=request_id,
        details={"resource": "paper-order", "note": "safe"},
    )


def test_append_list_and_chain_verification(tmp_path):
    with SQLiteAuditStore(tmp_path / "audit.db") as store:
        first = store.append(event("login"))
        second = store.append(event("order.check", "req-2"))
        assert (first, second) == (1, 2)
        assert store.verify_chain() is True
        records = store.list(10)
        assert [item.action for item in records] == ["order.check", "login"]


def test_database_triggers_block_update_and_delete(tmp_path):
    path = tmp_path / "audit.db"
    with SQLiteAuditStore(path) as store:
        store.append(event("login"))
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store._conn.execute("UPDATE audit_events SET actor='attacker' WHERE sequence=1")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store._conn.execute("DELETE FROM audit_events WHERE sequence=1")


def test_chain_detects_tampering(tmp_path):
    path = tmp_path / "audit.db"
    with SQLiteAuditStore(path) as store:
        store.append(event("login"))
        store.append(event("order.check", "req-2"))
        store._conn.execute("UPDATE audit_events SET details_json='{}' WHERE sequence=2")
        store._conn.rollback()
        # Direct database connection simulates an administrator modifying the file.
        store.close()

    raw = sqlite3.connect(path)
    raw.execute("PRAGMA writable_schema = ON") if False else None
    # The normal SQL path is protected by triggers; corruption is tested by changing
    # the stored hash through a separate connection after dropping only the trigger.
    raw.execute("DROP TRIGGER audit_events_no_update")
    raw.execute("UPDATE audit_events SET event_hash='tampered' WHERE sequence=2")
    raw.commit()
    raw.close()

    with SQLiteAuditStore(path) as store:
        with pytest.raises(AuditIntegrityError, match="hash"):
            store.verify_chain()


def test_details_are_serialized_without_requiring_json_safe_order(tmp_path):
    with SQLiteAuditStore(tmp_path / "audit.db") as store:
        store.append(AuditEvent.create("x", "a", "ok", details={"b": 2, "a": True}))
        assert store.verify_chain()
