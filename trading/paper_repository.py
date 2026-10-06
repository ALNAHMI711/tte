"""Persistence boundary for the paper-trading ledger.

The broker owns trading-domain state; repositories own persistence mechanics.
SQLite is the first durable backend and can later be replaced by PostgreSQL
without changing order/position semantics.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import ContextManager, Protocol
import sqlite3

from trading.paper_types import PaperOrderRecord


class PaperLedgerRepository(Protocol):
    """Minimal persistence contract required by PaperBroker."""

    def load_orders(self) -> tuple[PaperOrderRecord, ...]: ...

    def insert_order(self, order: PaperOrderRecord) -> None: ...

    def transaction(self) -> ContextManager[None]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class SQLitePaperLedgerRepository:
    """SQLite implementation of the paper-ledger persistence contract."""

    connection: sqlite3.Connection

    @classmethod
    def open(cls, path: str) -> "SQLitePaperLedgerRepository":
        connection = sqlite3.connect(path, timeout=5.0, check_same_thread=False)
        connection.execute(
            """CREATE TABLE IF NOT EXISTS paper_orders (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                client_order_id TEXT UNIQUE,
                status TEXT NOT NULL
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_orders_symbol "
            "ON paper_orders(symbol)"
        )
        connection.commit()
        return cls(connection)

    def load_orders(self) -> tuple[PaperOrderRecord, ...]:
        rows = self.connection.execute(
            "SELECT id, symbol, side, quantity, price, client_order_id, status "
            "FROM paper_orders ORDER BY rowid"
        ).fetchall()
        return tuple(
            PaperOrderRecord(
                id=row[0],
                symbol=row[1],
                side=row[2],
                quantity=row[3],
                price=row[4],
                client_order_id=row[5],
                status=row[6],
            )
            for row in rows
        )

    def insert_order(self, order: PaperOrderRecord) -> None:
        self.connection.execute(
            "INSERT INTO paper_orders "
            "(id, symbol, side, quantity, price, client_order_id, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                order.id,
                order.symbol,
                order.side,
                order.quantity,
                order.price,
                order.client_order_id,
                order.status,
            ),
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()
