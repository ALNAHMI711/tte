"""Persistence-neutral paper order record types."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperOrderRecord:
    id: str
    symbol: str
    side: str
    quantity: float | int | None
    price: float | int | None
    client_order_id: str | None
    status: str
