"""Unit tests for the trading clock and IST schedule phases."""

from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from finlaya.scheduler.trading_clock import SessionPhase, TradingClock
from finlaya.utils.time import IST


def test_trading_clock_phases():
    clock = TradingClock(start_time_str="09:27:00", force_exit_time_str="15:13:00")

    # 1. Before market start (e.g. 09:15 IST)
    dt_before = datetime(2026, 9, 29, 9, 15, 0, tzinfo=IST)
    assert clock.get_phase(dt_before) == SessionPhase.WAITING_FOR_OPEN
    assert clock.seconds_until_start(dt_before) == 12 * 60  # 720s

    # 2. Exactly at start (09:27 IST)
    dt_start = datetime(2026, 9, 29, 9, 27, 0, tzinfo=IST)
    assert clock.get_phase(dt_start) == SessionPhase.ACTIVE_TRADING

    # 3. Mid-day active session (12:30 IST)
    dt_mid = datetime(2026, 9, 29, 12, 30, 0, tzinfo=IST)
    assert clock.get_phase(dt_mid) == SessionPhase.ACTIVE_TRADING

    # 4. At forced exit time (15:13 IST)
    dt_exit = datetime(2026, 9, 29, 15, 13, 0, tzinfo=IST)
    assert clock.get_phase(dt_exit) == SessionPhase.FORCED_EXIT

    # 5. After forced exit (15:20 IST)
    dt_after = datetime(2026, 9, 29, 15, 20, 0, tzinfo=IST)
    assert clock.get_phase(dt_after) == SessionPhase.FORCED_EXIT
