"""Protocols, data classes, and domain exceptions for broker and market data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from finlaya.market.state import InstrumentQuote


class NiftyExpiryDayError(Exception):
    """Raised when today is determined to be a NIFTY expiry day."""


class ExpiryResolutionError(Exception):
    """Raised when authoritative NIFTY expiry information cannot be verified."""


class LotSizeMismatchError(Exception):
    """Raised when broker contract metadata does not match configured expected lot size."""


class MarketClosedError(Exception):
    """Raised when market is closed or unavailable for trading."""


@dataclass
class InstrumentMetadata:
    instrument_key: str
    trading_symbol: str
    strike_price: float
    expiry: str
    instrument_type: str  # CE or PE
    lot_size: int
    tick_size: float = 0.05
    exchange: str = "NSE"
    segment: str = "NSE_FO"


class MarketDataProvider(Protocol):
    """Abstract interface for live or replay market data feeds."""

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    def subscribe(self, instrument_keys: list[str]) -> None: ...
    def unsubscribe(self, instrument_keys: list[str]) -> None: ...
    def is_connected(self) -> bool: ...
