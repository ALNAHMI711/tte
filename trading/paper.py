"""Deterministic paper-trading ledger; no exchange writes."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import sqlite3
from threading import RLock
from uuid import uuid4

from trading.paper_repository import PaperLedgerRepository, SQLitePaperLedgerRepository
from trading.paper_types import PaperOrderRecord


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

    def __init__(
        self,
        persistence_path: str | None = None,
        *,
        repository: PaperLedgerRepository | None = None,
    ) -> None:
        self.orders: list[PaperOrder] = []
        self._by_client_id: dict[str, PaperOrder] = {}
        self._positions: dict[str, PaperPosition] = {}
        if persistence_path and repository is not None:
            raise ValueError("provide either persistence_path or repository, not both")
        self._persistence_path = persistence_path
        self._repository = repository
        self._lock = RLock()
        self._closed = False
        if self._repository is None and persistence_path:
            self._repository = SQLitePaperLedgerRepository.open(persistence_path)
        if self._repository is not None:
            self._restore()

    def healthcheck(self) -> None:
        """Verify the configured persistent paper store when one is in use."""
        with self._lock:
            if self._closed:
                raise RuntimeError("paper repository is closed")
            if self._repository is not None:
                try:
                    self._repository.healthcheck()
                except sqlite3.ProgrammingError as exc:
                    raise RuntimeError("paper repository is closed") from exc
            elif self._persistence_path:
                raise RuntimeError("paper repository is closed")

    @property
    def _connection(self) -> sqlite3.Connection | None:
        """Compatibility hook for tests and controlled SQLite inspection."""
        repository = self._repository
        if isinstance(repository, SQLitePaperLedgerRepository):
            return repository.connection
        return None

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
            if self._repository is None:
                return self._submit_memory(
                    symbol, side, quantity, price, client_order_id
                )

            try:
                with self._repository.transaction():
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
                            return existing

                    self._validate_fill(symbol, side, quantity)
                    order = PaperOrder(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        client_order_id=client_order_id,
                    )
                    self._repository.insert_order(
                        PaperOrderRecord(
                            id=order.id,
                            symbol=order.symbol,
                            side=order.side,
                            quantity=order.quantity,
                            price=order.price,
                            client_order_id=order.client_order_id,
                            status=order.status,
                        )
                    )
                    self.orders.append(order)
                    if client_order_id:
                        self._by_client_id[client_order_id] = order
                    self._apply_fill(order)
                    return order
            except Exception as exc:
                try:
                    self._reload_from_database()
                except Exception as recovery_exc:
                    raise RuntimeError(
                        "paper ledger recovery failed after transaction error"
                    ) from recovery_exc
                raise exc

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
            if self._repository is not None:
                self._reload_from_database()

    def reconcile(self, *, refresh: bool = True) -> PaperReconciliation:
        """Verify that the current positions are exactly reproducible from orders."""
        with self._lock:
            if refresh and self._repository is not None:
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

                if order.side == "sell":
                    current = rebuilt.get(order.symbol)
                    if current is None or order.quantity > current.quantity:
                        errors.append(
                            f"order {order.id} oversells {order.symbol}"
                        )
                        continue

                self._apply_fill_to(rebuilt, order)

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
        assert self._repository is not None

        restored_orders: list[PaperOrder] = []
        restored_by_client_id: dict[str, PaperOrder] = {}
        restored_positions: dict[str, PaperPosition] = {}

        rows = self._repository.load_orders()
        for row in rows:
            try:
                quantity = float(row.quantity)
                price = float(row.price)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    "paper ledger contains invalid numeric data"
                ) from exc

            order = PaperOrder(
                symbol=str(row.symbol).strip().upper(),
                side=str(row.side).strip().lower(),
                quantity=quantity,
                price=price,
                client_order_id=row.client_order_id,
                id=row.id,
                status=row.status,
            )
            if order.status != "FILLED":
                raise ValueError("paper ledger contains unsupported order status")
            if not math.isfinite(order.quantity) or not math.isfinite(order.price):
                raise ValueError("paper ledger contains invalid numeric data")
            if (
                not order.symbol
                or order.side not in VALID_SIDES
                or order.quantity <= 0
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
        self._apply_fill_to(self._positions, order)

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
            if self._repository is not None:
                self._repository.close()
                self._repository = None
            self._closed = True
