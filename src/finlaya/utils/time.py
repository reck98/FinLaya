"""Time utilities with explicit Asia/Kolkata (IST) timezone awareness."""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Return the current datetime in Asia/Kolkata timezone."""
    return datetime.now(IST)


def to_ist(dt: datetime) -> datetime:
    """Convert a datetime to Asia/Kolkata timezone.
    
    If naive, assume UTC or localize to IST safely.
    """
    if dt.tzinfo is None:
        # If naive, assume IST directly as FinLaya operates in IST
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def parse_ist_time(time_str: str) -> dt_time:
    """Parse a 'HH:MM:SS' string into a time object."""
    parts = [int(p) for p in time_str.split(":")]
    if len(parts) == 2:
        return dt_time(parts[0], parts[1], 0)
    elif len(parts) == 3:
        return dt_time(parts[0], parts[1], parts[2])
    raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM or HH:MM:SS")


def is_same_day(d1: date | datetime, d2: date | datetime) -> bool:
    """Check if two date/datetime instances represent the exact same calendar day."""
    val1 = d1.date() if isinstance(d1, datetime) else d1
    val2 = d2.date() if isinstance(d2, datetime) else d2
    return val1 == val2


def seconds_until(target_time: dt_time, from_dt: datetime | None = None) -> float:
    """Calculate remaining seconds from `from_dt` (or now_ist()) to `target_time` today.
    
    If target_time has already passed today, returns 0.0.
    """
    now = from_dt if from_dt is not None else now_ist()
    now_in_ist = to_ist(now)
    target_dt = datetime.combine(now_in_ist.date(), target_time, tzinfo=IST)
    diff = (target_dt - now_in_ist).total_seconds()
    return max(0.0, diff)


class MonotonicScheduler:
    """Fixed-cadence interval scheduler based on a monotonic clock.
    
    Prevents clock drift and handles inference latency gracefully.
    If an execution cycle takes longer than `interval_seconds`,
    subsequent ticks are serialized and elapsed ticks are skipped
    without accumulating backpressure.
    """

    def __init__(self, interval_seconds: float = 0.5):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.interval_seconds = interval_seconds
        self._start_time: float | None = None
        self._tick_count: int = 0

    def start(self) -> None:
        """Start or restart the scheduler clock."""
        self._start_time = time.monotonic()
        self._tick_count = 0

    async def sleep_until_next_tick(self) -> float:
        """Sleep until the next scheduled tick.
        
        Returns the latency/drift in seconds from scheduled tick time.
        """
        if self._start_time is None:
            self.start()
            return 0.0

        self._tick_count += 1
        scheduled_target = self._start_time + (self._tick_count * self.interval_seconds)
        now = time.monotonic()
        remaining = scheduled_target - now

        if remaining > 0:
            await asyncio.sleep(remaining)
            drift = time.monotonic() - scheduled_target
            return drift
        else:
            # Inference or execution took longer than interval.
            # Skip missed ticks to align to the next future boundary.
            missed_ticks = int((-remaining) // self.interval_seconds) + 1
            self._tick_count += missed_ticks
            next_target = self._start_time + (self._tick_count * self.interval_seconds)
            delay_to_next = max(0.0, next_target - time.monotonic())
            if delay_to_next > 0:
                await asyncio.sleep(delay_to_next)
            return abs(remaining)
