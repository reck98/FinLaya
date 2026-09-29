"""1-minute candle aggregator and historical sliding window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from pydantic import BaseModel
from finlaya.utils.time import to_ist


class Candle(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass
class _OngoingCandle:
    minute_bucket: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class CandleEngine:
    """Maintains a rolling window of completed 1-minute candles from live ticks or historical loads."""

    def __init__(self, max_candles: int = 6):
        self.max_candles = max_candles
        self._completed_candles: list[Candle] = []
        self._ongoing: _OngoingCandle | None = None

    def seed_historical_candles(self, candles: list[Candle]) -> None:
        """Seed completed historical candles (oldest first)."""
        self._completed_candles = candles[-self.max_candles:]

    def add_tick(self, timestamp: datetime, price: float, volume: int = 0) -> Candle | None:
        """Process a live tick.
        
        If a new minute begins, the previous ongoing candle is completed and returned.
        """
        ts = to_ist(timestamp)
        bucket = ts.replace(second=0, microsecond=0)

        completed: Candle | None = None

        if self._ongoing is None:
            self._ongoing = _OngoingCandle(
                minute_bucket=bucket,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
            )
        elif bucket > self._ongoing.minute_bucket:
            # Finalize previous candle
            completed = Candle(
                timestamp=self._ongoing.minute_bucket.isoformat(),
                open=self._ongoing.open,
                high=self._ongoing.high,
                low=self._ongoing.low,
                close=self._ongoing.close,
                volume=self._ongoing.volume,
            )
            self._completed_candles.append(completed)
            if len(self._completed_candles) > self.max_candles:
                self._completed_candles.pop(0)

            # Start new ongoing candle
            self._ongoing = _OngoingCandle(
                minute_bucket=bucket,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
            )
        else:
            # Update current ongoing candle
            self._ongoing.high = max(self._ongoing.high, price)
            self._ongoing.low = min(self._ongoing.low, price)
            self._ongoing.close = price
            self._ongoing.volume += volume

        return completed

    def get_completed_candles(self) -> list[Candle]:
        """Return the latest completed candles (up to max_candles)."""
        return list(self._completed_candles)
