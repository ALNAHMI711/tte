"""Normalized exchange-adapter contracts with a hard live-trading safety boundary."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .execution import OrderRequest
from .market import Candle, OrderBookSnapshot


class TradingEnvironment(str, Enum):
    TESTNET = "testnet"
    LIVE = "live"


@dataclass(frozen=True)
class AdapterCapabilities:
    market_data: bool = True
    spot: bool = False
    cross_margin: bool = False
    isolated_margin: bool = False
    usd_m_futures: bool = False
    coin_m_futures: bool = False
    withdrawals: bool = False


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    environment: TradingEnvironment
    can_trade: bool
    can_withdraw: bool
    balances: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    base_asset: str
    quote_asset: str
    min_quantity: float
    quantity_step: float
    min_notional: float

    def validate(self) -> None:
        if not self.symbol or not self.base_asset or not self.quote_asset:
            raise ValueError("symbol metadata is incomplete")
        if self.min_quantity <= 0 or self.quantity_step <= 0 or self.min_notional < 0:
            raise ValueError("symbol limits must be valid positive values")


class AdapterError(RuntimeError):
    """Base class for normalized adapter failures."""


class LiveTradingBlocked(AdapterError):
    """Raised when a live-capable operation is attempted before live gates pass."""


class WithdrawalPermissionError(AdapterError):
    """Raised when an account exposes withdrawal permission."""


class ExchangeAdapter(Protocol):
    """Provider-neutral contract consumed by market/execution services."""

    name: str
    environment: TradingEnvironment
    capabilities: AdapterCapabilities

    def ping(self) -> bool: ...
    def account_snapshot(self) -> AccountSnapshot: ...
    def symbol_info(self, symbol: str) -> SymbolInfo: ...
    def ticker(self, symbol: str) -> tuple[float, float]: ...
    def order_book(self, symbol: str, limit: int = 20) -> OrderBookSnapshot: ...
    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> tuple[Candle, ...]: ...
    def submit_order(self, request: OrderRequest) -> object: ...


def enforce_safe_account(account: AccountSnapshot) -> None:
    """Reject accounts that permit withdrawals; trading keys must be trade-only."""
    if account.can_withdraw:
        raise WithdrawalPermissionError("withdrawal permission must be disabled")


def enforce_environment(environment: TradingEnvironment, *, allow_live: bool = False) -> None:
    """Require explicit opt-in before any live environment can be selected."""
    if environment is TradingEnvironment.LIVE and not allow_live:
        raise LiveTradingBlocked("live environment is disabled")


class SafeAdapter:
    """Reusable base for adapters; subclasses provide provider-specific I/O.

    This class intentionally cannot execute live orders unless an explicit
    application-level gate is passed by the future production execution layer.
    """

    def __init__(self, name: str, environment: TradingEnvironment, capabilities: AdapterCapabilities) -> None:
        if not name:
            raise ValueError("adapter name is required")
        enforce_environment(environment)
        self.name = name
        self.environment = environment
        self.capabilities = capabilities

    def submit_order(self, request: OrderRequest) -> object:
        if self.environment is TradingEnvironment.LIVE:
            raise LiveTradingBlocked("live order routing is disabled")
        raise NotImplementedError("adapter order routing is not implemented")
