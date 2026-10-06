"""Normalized exchange-adapter contracts with a hard live-trading safety boundary."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .execution import OrderRequest
from .market import BinanceMarketData, Candle, OrderBookSnapshot


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
    price_tick_size: float = 0.0

    def validate(self) -> None:
        if not self.symbol or not self.base_asset or not self.quote_asset:
            raise ValueError("symbol metadata is incomplete")
        if self.min_quantity <= 0 or self.quantity_step <= 0 or self.min_notional < 0:
            raise ValueError("symbol limits must be valid positive values")
        if self.price_tick_size < 0:
            raise ValueError("price tick size must be non-negative")


class AdapterError(RuntimeError):
    """Base class for normalized adapter failures."""


class LiveTradingBlocked(AdapterError):
    """Raised when a live-capable operation is attempted before live gates pass."""


class WithdrawalPermissionError(AdapterError):
    """Raised when an account exposes withdrawal permission."""


class ExchangeAdapter(Protocol):
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
    if account.can_withdraw:
        raise WithdrawalPermissionError("withdrawal permission must be disabled")


def enforce_environment(environment: TradingEnvironment, *, allow_live: bool = False) -> None:
    if environment is TradingEnvironment.LIVE and not allow_live:
        raise LiveTradingBlocked("live environment is disabled")


class SafeAdapter:
    """Reusable base for adapters; live routing is always fail-closed."""

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


class BinanceSpotTestnetAdapter(SafeAdapter):
    """Provider adapter for public Spot Testnet market data only."""

    def __init__(self, market_data: BinanceMarketData | None = None) -> None:
        super().__init__(
            name="binance-spot-testnet",
            environment=TradingEnvironment.TESTNET,
            capabilities=AdapterCapabilities(market_data=True, spot=True),
        )
        self.market_data = market_data or BinanceMarketData()

    def ping(self) -> bool:
        try:
            self.market_data.order_book("BTCUSDT", limit=1)
        except Exception:
            return False
        return True

    def account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            account_id="testnet-public",
            environment=self.environment,
            can_trade=False,
            can_withdraw=False,
        )

    def symbol_info(self, symbol: str) -> SymbolInfo:
        raw = self.market_data.exchange_info(symbol)
        info = SymbolInfo(
            symbol=raw.symbol,
            base_asset=raw.base_asset,
            quote_asset=raw.quote_asset,
            min_quantity=raw.min_quantity,
            quantity_step=raw.quantity_step,
            min_notional=raw.min_notional,
            price_tick_size=raw.price_tick_size,
        )
        info.validate()
        return info

    def ticker(self, symbol: str) -> tuple[float, float]:
        book = self.market_data.order_book(symbol, limit=1)
        if not book.bids or not book.asks:
            raise AdapterError("order book has no two-sided market")
        return book.bids[0][0], book.asks[0][0]

    def order_book(self, symbol: str, limit: int = 20) -> OrderBookSnapshot:
        return self.market_data.order_book(symbol, limit=limit)

    def candles(self, symbol: str, timeframe: str, limit: int = 200) -> tuple[Candle, ...]:
        return self.market_data.klines(symbol, timeframe, limit=limit)

    def submit_order(self, request: OrderRequest) -> object:
        raise LiveTradingBlocked("Binance Spot Testnet adapter is read-only in this foundation")
