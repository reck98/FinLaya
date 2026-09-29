"""Trading day scheduler enforcing 09:27 start and 15:13 forced exit in Asia/Kolkata."""

from __future__ import annotations

import asyncio
from datetime import datetime, time as dt_time
from enum import Enum

from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from finlaya.utils.time import IST, MonotonicScheduler, now_ist, parse_ist_time, seconds_until, to_ist

logger = get_logger("trading_clock")


class SessionPhase(str, Enum):
    WAITING_FOR_OPEN = "WAITING_FOR_OPEN"
    ACTIVE_TRADING = "ACTIVE_TRADING"
    FORCED_EXIT = "FORCED_EXIT"
    POST_SESSION = "POST_SESSION"


class TradingClock:
    """Manages the trading schedule in Asia/Kolkata timezone."""

    def __init__(
        self,
        start_time_str: str = "09:27:00",
        force_exit_time_str: str = "15:13:00",
        decision_interval_seconds: float = 0.5,
    ):
        self.start_time: dt_time = parse_ist_time(start_time_str)
        self.force_exit_time: dt_time = parse_ist_time(force_exit_time_str)
        self.scheduler = MonotonicScheduler(decision_interval_seconds)

    def get_phase(self, current_dt: datetime | None = None) -> SessionPhase:
        """Determine current trading session phase."""
        now = to_ist(current_dt or now_ist())
        now_time = now.time()

        if now_time < self.start_time:
            return SessionPhase.WAITING_FOR_OPEN
        elif now_time < self.force_exit_time:
            return SessionPhase.ACTIVE_TRADING
        else:
            return SessionPhase.FORCED_EXIT

    def seconds_until_start(self, current_dt: datetime | None = None) -> float:
        return seconds_until(self.start_time, current_dt)

    def seconds_until_forced_exit(self, current_dt: datetime | None = None) -> float:
        return seconds_until(self.force_exit_time, current_dt)

    async def wait_until_start(self) -> None:
        """Asynchronously wait until 09:27:00 Asia/Kolkata if started early."""
        rem = self.seconds_until_start()
        if rem > 0:
            logger.info(
                f"Pre-market wait: Waiting {rem:.1f}s until trading session start ({self.start_time.strftime('%H:%M:%S')} IST)..."
            )
            # Sleep in intervals to log periodic heartbeats
            while rem > 0:
                step = min(rem, 30.0)
                await asyncio.sleep(step)
                rem = self.seconds_until_start()
                if rem > 0:
                    logger.info(f"{rem:.0f}s remaining until trading start at {self.start_time.strftime('%H:%M:%S')} IST")
            logger.info("Market session time reached: 09:27:00 IST. Starting strategy loop.", LogEvent.APPLICATION_START)
