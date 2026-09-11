from decimal import Decimal

import pytest

from trading.adapters import SymbolInfo
from trading.order_filters import (
    OrderFilterError,
    floor_to_step,
    normalize_and_validate_order,
    normalize_quantity,
    validate_notional,
)


SYMBOL = SymbolInfo(
    symbol="BTCUSDT",
    base_asset="BTC",
    quote_asset="USDT",
    min_quantity=Decimal("0.001"),
    quantity_step=Decimal("0.001"),
    min_notional=Decimal("10"),
)


def test_floor_to_step_never_rounds_up() -> None:
    assert floor_to_step("0.1239", "0.001") == Decimal("0.123")
    assert floor_to_step("1.999", "0.1") == Decimal("1.9")


def test_normalize_quantity_accepts_exact_step() -> None:
    assert normalize_quantity("0.123", SYMBOL) == Decimal("0.123")


def test_normalize_quantity_rejects_after_floor_below_minimum() -> None:
    with pytest.raises(OrderFilterError, match="below exchange minimum"):
        normalize_quantity("0.0009", SYMBOL)


def test_min_notional_is_enforced_after_quantity_normalization() -> None:
    with pytest.raises(OrderFilterError, match="notional"):
        validate_notional("0.0099", "1000", SYMBOL)


def test_exact_min_notional_is_accepted() -> None:
    assert validate_notional("0.01", "1000", SYMBOL) == Decimal("10.00")


def test_combined_order_result_is_deterministic() -> None:
    result = normalize_and_validate_order("0.1239", "100.00", SYMBOL)
    assert result.quantity == Decimal("0.123")
    assert result.price == Decimal("100.00")
    assert result.notional == Decimal("12.30000")


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_invalid_quantity_is_rejected(value: object) -> None:
    with pytest.raises(OrderFilterError):
        normalize_quantity(value, SYMBOL)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_invalid_price_is_rejected(value: object) -> None:
    with pytest.raises(OrderFilterError):
        validate_notional("0.01", value, SYMBOL)


def test_notional_failure_does_not_auto_increase_quantity() -> None:
    with pytest.raises(OrderFilterError, match="notional"):
        normalize_and_validate_order("0.0101", "999", SYMBOL)
