"""Persistence boundary for the paper-trading ledger.

The broker owns trading-domain state; repositories own persistence mechanics.
SQLite is the first durable backend and can later be replaced by PostgreSQL
without changing order/position semantics.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import ContextManager, Iterator, Protocol, Any
import sqlite3

from trading.paper_types import PaperOrderRecord


class PaperLedgerRepository(Protocol):
    """Minimal persistence contract required by PaperBroker."""

    def load_orders(self) -> tuple[PaperOrderRecord, ...]: ...

    def insert_order(self, order: PaperOrderRecord) -> None: ...

    def transaction(self) -> ContextManager[None]: ...

    def close(self) -> None: ...


class PostgresPaperLedgerRepository:
    """PostgreSQL repository using psycopg; optional until PostgreSQL is enabled."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @classmethod
    def open(cls, dsn: str) -> "PostgresPaperLedgerRepository":
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL paper storage requires the postgres dependency"
            ) from exc
        connection = psycopg.connect(dsn)
        repository = cls(connection)
        repository._initialize_schema()
        return repository

    def _initialize_schema(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS paper_orders (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity DOUBLE PRECISION NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    client_order_id TEXT UNIQUE,
                    status TEXT NOT NULL
                )"""
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_paper_orders_symbol "
                "ON paper_orders(symbol)"
            )
        self.connection.commit()

    def load_orders(self) -> tuple[PaperOrderRecord, ...]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, symbol, side, quantity, price, client_order_id, status "
                "FROM paper_orders ORDER BY id"
            )
            return tuple(PaperOrderRecord(*row) for row in cursor.fetchall())

    def insert_order(self, order: PaperOrderRecord) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO paper_orders "
                "(id, symbol, side, quantity, price, client_order_id, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (order.id, order.symbol, order.side, order.quantity, order.price,
                 order.client_order_id, order.status),
            )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()


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
