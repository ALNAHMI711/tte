"""Deterministic paper-trading ledger; no exchange writes."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class PaperOrder:
    symbol: str
    side: str
    quantity: float
    price: float
    id: str = field(default_factory=lambda: f"paper-{uuid4().hex}")
    status: str = "FILLED"


class PaperBroker:
    def __init__(self) -> None:
        self.orders: list[PaperOrder] = []

    def submit(self, symbol: str, side: str, quantity: float, price: float) -> PaperOrder:
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")
        order = PaperOrder(symbol=symbol, side=side, quantity=quantity, price=price)
        self.orders.append(order)
        return order
