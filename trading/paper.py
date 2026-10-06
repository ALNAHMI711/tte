"""Deterministic paper-trading ledger; no exchange writes."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import sqlite3
from threading import RLock
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


@dataclass(frozen=True)
class PaperReconciliation:
    """Result of checking that positions match the filled-order ledger."""

    valid: bool
    order_count: int
    position_count: int
    errors: tuple[str, ...] = ()


class PaperBroker:
    """Persistent or in-memory paper ledger with deterministic fills."""

    def __init__(self, persistence_path: str | None = None) -> None:
        self.orders: list[PaperOrder] = []
        self._by_client_id: dict[str, PaperOrder] = {}
        self._positions: dict[str, PaperPosition] = {}
        self._persistence_path = persistence_path
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()
        if persistence_path:
            self._connection = sqlite3.connect(
                persistence_path, timeout=5.0, check_same_thread=False
            )
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
        if (
            not math.isfinite(quantity)
            or not math.isfinite(price)
            or quantity <= 0
            or price <= 0
        ):
            raise ValueError("quantity and price must be positive finite values")

        if client_order_id:
            client_order_id = client_order_id.strip() or None

        with self._lock:
            if self._connection is None:
                return self._submit_memory(
                    symbol, side, quantity, price, client_order_id
                )

            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._reload_from_database()

                if client_order_id:
                    existing = self._by_client_id.get(client_order_id)
                    if existing is not None:
                        if (
                            existing.symbol != symbol
                            or existing.side != side
                            or existing.quantity != quantity
                            or existing.price != price
                        ):
                            raise ValueError(
                                "client_order_id is already bound to a different order"
                            )
                        self._connection.rollback()
                        return existing

                self._validate_fill(symbol, side, quantity)
                order = PaperOrder(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    client_order_id=client_order_id,
                )
                self._connection.execute(
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
                self.orders.append(order)
                if client_order_id:
                    self._by_client_id[client_order_id] = order
                self._apply_fill(order)
                self._connection.commit()
                return order
            except Exception:
                self._connection.rollback()
                self._reload_from_database()
                raise

    def _submit_memory(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        client_order_id: str | None,
    ) -> PaperOrder:
        if client_order_id:
            existing = self._by_client_id.get(client_order_id)
            if existing is not None:
                if (
                    existing.symbol != symbol
                    or existing.side != side
                    or existing.quantity != quantity
                    or existing.price != price
                ):
                    raise ValueError(
                        "client_order_id is already bound to a different order"
                    )
                return existing

        self._validate_fill(symbol, side, quantity)
        order = PaperOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )
        self.orders.append(order)
        if client_order_id:
            self._by_client_id[client_order_id] = order
        self._apply_fill(order)
        return order

    def _validate_fill(self, symbol: str, side: str, quantity: float) -> None:
        if side == "sell":
            current = self._positions.get(symbol)
            if current is None or quantity > current.quantity:
                raise ValueError("paper sell exceeds current position")

    def _restore(self) -> None:
        with self._lock:
            self._reload_from_database()

    def refresh(self) -> None:
        """Reload persistent state so another broker instance's commits are visible."""
        with self._lock:
            if self._connection is not None:
                self._reload_from_database()

    def reconcile(self, *, refresh: bool = True) -> PaperReconciliation:
        """Verify that the current positions are exactly reproducible from orders."""
        with self._lock:
            if refresh and self._connection is not None:
                self._reload_from_database()

            errors: list[str] = []
            rebuilt: dict[str, PaperPosition] = {}
            seen_client_ids: set[str] = set()

            for order in self.orders:
                if order.status != "FILLED":
                    errors.append(
                        f"order {order.id} has unsupported status {order.status!r}"
                    )
                    continue
                if (
                    not order.symbol
                    or order.side not in VALID_SIDES
                    or not math.isfinite(order.quantity)
                    or order.quantity <= 0
                    or not math.isfinite(order.price)
                    or order.price <= 0
                ):
                    errors.append(f"order {order.id} contains invalid data")
                    continue
                if order.client_order_id:
                    if order.client_order_id in seen_client_ids:
                        errors.append(
                            f"duplicate client order id {order.client_order_id!r}"
                        )
                    seen_client_ids.add(order.client_order_id)

                current = rebuilt.get(order.symbol)
                if order.side == "sell":
                    if current is None or order.quantity > current.quantity:
                        errors.append(
                            f"order {order.id} oversells {order.symbol}"
                        )
                        continue
                    remaining = current.quantity - order.quantity
                    if remaining <= 0:
                        rebuilt.pop(order.symbol, None)
                    else:
                        rebuilt[order.symbol] = PaperPosition(
                            order.symbol, remaining, current.average_price
                        )
                    continue

                if current is None:
                    rebuilt[order.symbol] = PaperPosition(
                        order.symbol, order.quantity, order.price
                    )
                else:
                    total_qty = current.quantity + order.quantity
                    average = (
                        (current.quantity * current.average_price)
                        + (order.quantity * order.price)
                    ) / total_qty
                    rebuilt[order.symbol] = PaperPosition(
                        order.symbol, total_qty, average
                    )

            if rebuilt != self._positions:
                errors.append("positions do not match the filled-order ledger")

            return PaperReconciliation(
                valid=not errors,
                order_count=len(self.orders),
                position_count=len(self._positions),
                errors=tuple(errors),
            )

    def _reload_from_database(self) -> None:
        """Rebuild state off to the side, then publish it atomically.

        A corrupt persistent row must never leave a live broker half-restored.
        """
        assert self._connection is not None

        restored_orders: list[PaperOrder] = []
        restored_by_client_id: dict[str, PaperOrder] = {}
        restored_positions: dict[str, PaperPosition] = {}

        rows = self._connection.execute(
            "SELECT id, symbol, side, quantity, price, client_order_id, status "
            "FROM paper_orders ORDER BY rowid"
        ).fetchall()
        for row in rows:
            order = PaperOrder(
                symbol=str(row[1]).strip().upper(),
                side=str(row[2]).strip().lower(),
                quantity=float(row[3]),
                price=float(row[4]),
                client_order_id=row[5],
                id=row[0],
                status=row[6],
            )
            if order.status != "FILLED":
                raise ValueError("paper ledger contains unsupported order status")
            if (
                not order.symbol
                or order.side not in VALID_SIDES
                or not math.isfinite(order.quantity)
                or order.quantity <= 0
                or not math.isfinite(order.price)
                or order.price <= 0
            ):
                raise ValueError("paper ledger contains invalid order data")
            if order.client_order_id:
                if order.client_order_id in restored_by_client_id:
                    raise ValueError("paper ledger contains duplicate client order ids")
                restored_by_client_id[order.client_order_id] = order
            self._validate_fill_against(
                restored_positions, order.symbol, order.side, order.quantity
            )
            restored_orders.append(order)
            self._apply_fill_to(restored_positions, order)

        self.orders[:] = restored_orders
        self._by_client_id.clear()
        self._by_client_id.update(restored_by_client_id)
        self._positions.clear()
        self._positions.update(restored_positions)

    @staticmethod
    def _validate_fill_against(
        positions: dict[str, PaperPosition],
        symbol: str,
        side: str,
        quantity: float,
    ) -> None:
        if side == "sell":
            current = positions.get(symbol)
            if current is None or quantity > current.quantity:
                raise ValueError("paper ledger contains invalid sell")

    @staticmethod
    def _apply_fill_to(
        positions: dict[str, PaperPosition], order: PaperOrder
    ) -> None:
        current = positions.get(order.symbol)
        if order.side == "buy":
            if current is None:
                positions[order.symbol] = PaperPosition(
                    order.symbol, order.quantity, order.price
                )
                return
            total_qty = current.quantity + order.quantity
            average = (
                (current.quantity * current.average_price)
                + (order.quantity * order.price)
            ) / total_qty
            positions[order.symbol] = PaperPosition(
                order.symbol, total_qty, average
            )
            return

        remaining = current.quantity - order.quantity if current else 0.0
        if remaining <= 0:
            positions.pop(order.symbol, None)
        else:
            positions[order.symbol] = PaperPosition(
                order.symbol, remaining, current.average_price
            )

    def _apply_fill(self, order: PaperOrder) -> None:
        current = self._positions.get(order.symbol)
        if order.side == "buy":
            if current is None:
                self._positions[order.symbol] = PaperPosition(
                    order.symbol, order.quantity, order.price
                )
                return
            total_qty = current.quantity + order.quantity
            average = (
                (current.quantity * current.average_price)
                + (order.quantity * order.price)
            ) / total_qty
            self._positions[order.symbol] = PaperPosition(
                order.symbol, total_qty, average
            )
            return

        remaining = current.quantity - order.quantity if current else 0.0
        if remaining <= 0:
            self._positions.pop(order.symbol, None)
        else:
            self._positions[order.symbol] = PaperPosition(
                order.symbol, remaining, current.average_price
            )

    def order_by_client_id(self, client_order_id: str) -> PaperOrder | None:
        normalized = client_order_id.strip()
        if not normalized:
            return None
        with self._lock:
            return self._by_client_id.get(normalized)

    def position(self, symbol: str) -> PaperPosition | None:
        with self._lock:
            return self._positions.get(symbol.strip().upper())

    def positions(self) -> tuple[PaperPosition, ...]:
        with self._lock:
            return tuple(
                sorted(self._positions.values(), key=lambda item: item.symbol)
            )

    def orders_for(self, symbol: str) -> tuple[PaperOrder, ...]:
        normalized = symbol.strip().upper()
        with self._lock:
            return tuple(order for order in self.orders if order.symbol == normalized)

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
