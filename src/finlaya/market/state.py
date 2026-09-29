"""In-memory market data cache and staleness tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from finlaya.utils.time import now_ist


@dataclass
class InstrumentQuote:
    instrument_key: str
    ltp: float = 0.0
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    prev_close: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    volume: int = 0
    oi: int = 0
    prev_oi: int | None = None
    oi_change: int | None = None
    bid: float | None = None
    bid_qty: int | None = None
    ask: float | None = None
    ask_qty: int | None = None
    updated_at: float = field(default_factory=time.monotonic)
    ist_time: datetime = field(default_factory=now_ist)


class MarketDataCache:
    """Thread-safe / async-safe in-memory cache for live instrument quotes."""

    def __init__(self):
        self._quotes: dict[str, InstrumentQuote] = {}
        self._last_global_update: float = 0.0

    def update_quote(self, quote: InstrumentQuote) -> None:
        self._quotes[quote.instrument_key] = quote
        self._last_global_update = time.monotonic()

    def get_quote(self, instrument_key: str) -> InstrumentQuote | None:
        return self._quotes.get(instrument_key)

    def is_stale(self, instrument_key: str, max_staleness_seconds: float = 2.0) -> bool:
        """Check if quote for a specific instrument has not been updated within threshold."""
        quote = self._quotes.get(instrument_key)
        if quote is None:
            return True
        return (time.monotonic() - quote.updated_at) > max_staleness_seconds

    def are_instruments_fresh(self, instrument_keys: list[str], max_staleness_seconds: float = 2.0) -> bool:
        """Check if all required instruments have non-stale data."""
        if not instrument_keys:
            return False
        for key in instrument_keys:
            if self.is_stale(key, max_staleness_seconds):
                return False
        return True

    def get_staleness_seconds(self, instrument_key: str) -> float:
        """Return the number of seconds since last update for this instrument."""
        quote = self._quotes.get(instrument_key)
        if quote is None:
            return float("inf")
        return time.monotonic() - quote.updated_at
