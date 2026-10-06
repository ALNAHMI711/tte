"""Deterministic paper-trading ledger; no exchange writes."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import sqlite3
from uuid import uuid4


VALID_SIDES = {"buy", "sell"}


@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    quantity: float
    average_price: float


@dataclass
class PaperOrder:
    symbol: str
    side: str
    quantity: float
    price: float
    client_order_id: str | None = None
    id: str = field(default_factory=lambda: f"paper-{uuid4().hex}")
    status: str = "FILLED"


class PaperBroker:
    """In-memory paper ledger with deterministic fills and idempotent client IDs."""

    def __init__(self, persistence_path: str | None = None) -> None:
        self.orders: list[PaperOrder] = []
        self._by_client_id: dict[str, PaperOrder] = {}
        self._positions: dict[str, PaperPosition] = {}
        self._persistence_path = persistence_path
        self._connection: sqlite3.Connection | None = None
        if persistence_path:
            self._connection = sqlite3.connect(persistence_path)
            self._connection.execute(
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
            self._connection.commit()
            self._restore()

    def submit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        client_order_id: str | None = None,
    ) -> PaperOrder:
        symbol = symbol.strip().upper()
        side = side.strip().lower()
        if not symbol:
            raise ValueError("symbol is required")
        if side not in VALID_SIDES:
            raise ValueError("side must be buy or sell")
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")
        if client_order_id:
            client_order_id = client_order_id.strip()
            if not client_order_id:
                client_order_id = None
            else:
                existing = self._by_client_id.get(client_order_id)
                if existing is not None:
                    if (
                        existing.symbol != symbol
                        or existing.side != side
                        or existing.quantity != quantity
                        or existing.price != price
                    ):
                        raise ValueError("client_order_id is already bound to a different order")
                    return existing

        if side == "sell":
            current = self._positions.get(symbol)
            if current is None or quantity > current.quantity:
                raise ValueError("paper sell exceeds current position")

        order = PaperOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )
        if self._connection is not None:
            self._connection.execute(
                "INSERT INTO paper_orders (id, symbol, side, quantity, price, client_order_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order.id, order.symbol, order.side, order.quantity, order.price, order.client_order_id, order.status),
            )
            self._connection.commit()
        self.orders.append(order)
        if client_order_id:
            self._by_client_id[client_order_id] = order
        self._apply_fill(order)
        return order

    def _restore(self) -> None:
        assert self._connection is not None
        rows = self._connection.execute(
            "SELECT id, symbol, side, quantity, price, client_order_id, status FROM paper_orders ORDER BY rowid"
        ).fetchall()
        for row in rows:
            order = PaperOrder(
                symbol=row[1],
                side=row[2],
                quantity=float(row[3]),
                price=float(row[4]),
                client_order_id=row[5],
                id=row[0],
                status=row[6],
            )
            if (
                not math.isfinite(order.quantity) or order.quantity <= 0
                or not math.isfinite(order.price) or order.price <= 0
                or order.side not in VALID_SIDES
                or not order.symbol
            ):
                raise ValueError("paper ledger contains invalid order data")
            if order.client_order_id:
                if order.client_order_id in self._by_client_id:
                    raise ValueError("paper ledger contains duplicate client order ids")
                self._by_client_id[order.client_order_id] = order
            if order.side == "sell":
                current = self._positions.get(order.symbol)
                if current is None or order.quantity > current.quantity:
                    raise ValueError("paper ledger contains an invalid sell")
            self.orders.append(order)
            self._apply_fill(order)


    def _apply_fill(self, order: PaperOrder) -> None:
        current = self._positions.get(order.symbol)
        if order.side == "buy":
            if current is None:
                self._positions[order.symbol] = PaperPosition(order.symbol, order.quantity, order.price)
                return
            total_qty = current.quantity + order.quantity
            average = ((current.quantity * current.average_price) + (order.quantity * order.price)) / total_qty
            self._positions[order.symbol] = PaperPosition(order.symbol, total_qty, average)
            return

        remaining = current.quantity - order.quantity if current else 0.0
        if remaining <= 0:
            self._positions.pop(order.symbol, None)
        else:
            self._positions[order.symbol] = PaperPosition(order.symbol, remaining, current.average_price)

    def order_by_client_id(self, client_order_id: str) -> PaperOrder | None:
        normalized = client_order_id.strip()
        if not normalized:
            return None
        return self._by_client_id.get(normalized)

    def position(self, symbol: str) -> PaperPosition | None:
        return self._positions.get(symbol.strip().upper())

    def positions(self) -> tuple[PaperPosition, ...]:
        return tuple(sorted(self._positions.values(), key=lambda item: item.symbol))

    def orders_for(self, symbol: str) -> tuple[PaperOrder, ...]:
        normalized = symbol.strip().upper()
        return tuple(order for order in self.orders if order.symbol == normalized)
