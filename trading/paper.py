"""Deterministic paper-trading ledger; no exchange writes."""
from __future__ import annotations

from dataclasses import dataclass, field
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

    def __init__(self) -> None:
        self.orders: list[PaperOrder] = []
        self._by_client_id: dict[str, PaperOrder] = {}
        self._positions: dict[str, PaperPosition] = {}

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
            existing = self._by_client_id.get(client_order_id)
            if existing is not None:
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
        self.orders.append(order)
        if client_order_id:
            self._by_client_id[client_order_id] = order
        self._apply_fill(order)
        return order

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

    def position(self, symbol: str) -> PaperPosition | None:
        return self._positions.get(symbol.strip().upper())

    def positions(self) -> tuple[PaperPosition, ...]:
        return tuple(sorted(self._positions.values(), key=lambda item: item.symbol))

    def orders_for(self, symbol: str) -> tuple[PaperOrder, ...]:
        normalized = symbol.strip().upper()
        return tuple(order for order in self.orders if order.symbol == normalized)
