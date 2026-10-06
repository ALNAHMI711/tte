"""Persistence-neutral paper order record types."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperOrderRecord:
    id: str
    symbol: str
    side: str
    quantity: object
    price: object
    client_order_id: str | None
    status: str
