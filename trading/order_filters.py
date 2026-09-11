"""Deterministic, exchange-filter-aware order quantity and price validation."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
import math

from .adapters import SymbolInfo


class OrderFilterError(ValueError):
    """Raised when an order violates exchange constraints or is invalid."""


@dataclass(frozen=True)
class NormalizedOrder:
    quantity: Decimal
    price: Decimal
    notional: Decimal


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, float) and not math.isfinite(value):
        raise OrderFilterError(f"{field} must be finite")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OrderFilterError(f"{field} is invalid") from exc
    if not result.is_finite() or result <= 0:
        raise OrderFilterError(f"{field} must be positive and finite")
    return result


def floor_to_step(value: object, step: object) -> Decimal:
    """Floor a positive value to the exchange step without rounding upward."""
    amount = _decimal(value, "value")
    increment = _decimal(step, "step")
    units = (amount / increment).to_integral_value(rounding=ROUND_DOWN)
    return units * increment


def normalize_quantity(quantity: object, symbol: SymbolInfo) -> Decimal:
    """Normalize quantity downward and reject values below the minimum."""
    symbol.validate()
    requested = _decimal(quantity, "quantity")
    step = _decimal(symbol.quantity_step, "quantity_step")
    minimum = _decimal(symbol.min_quantity, "min_quantity")
    normalized = floor_to_step(requested, step)
    if normalized < minimum:
        raise OrderFilterError("quantity is below exchange minimum")
    return normalized


def validate_notional(quantity: object, price: object, symbol: SymbolInfo) -> Decimal:
    """Validate the final quantity-price notional without increasing quantity."""
    final_quantity = normalize_quantity(quantity, symbol)
    final_price = _decimal(price, "price")
    minimum = Decimal(str(symbol.min_notional))
    if minimum < 0 or not minimum.is_finite():
        raise OrderFilterError("min_notional is invalid")
    notional = final_quantity * final_price
    if notional < minimum:
        raise OrderFilterError("order notional is below exchange minimum")
    return notional


def normalize_and_validate_order(
    quantity: object, price: object, symbol: SymbolInfo
) -> NormalizedOrder:
    """Return a safe normalized order or reject it before any future submission."""
    final_quantity = normalize_quantity(quantity, symbol)
    final_price = _decimal(price, "price")
    notional = validate_notional(final_quantity, final_price, symbol)
    return NormalizedOrder(
        quantity=final_quantity,
        price=final_price,
        notional=notional,
    )
