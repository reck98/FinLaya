"""Unit tests for NIFTY expiry validation and fail-closed rules."""

from datetime import date
import pytest
from finlaya.broker.base import ExpiryResolutionError, NiftyExpiryDayError
from finlaya.broker.upstox_instruments import UpstoxInstrumentService


class DummyApiClient:
    pass


def test_verify_not_expiry_day_aborts_on_expiry():
    svc = UpstoxInstrumentService(DummyApiClient())
    expiries = ["2026-09-29", "2026-10-06", "2026-10-27"]
    today = date(2026, 9, 29)

    # Today is in expiries list -> MUST abort with NiftyExpiryDayError
    with pytest.raises(NiftyExpiryDayError, match="NIFTY_EXPIRY_DAY"):
        svc.verify_not_expiry_day(expiries, today=today)


def test_verify_not_expiry_day_succeeds_on_non_expiry():
    svc = UpstoxInstrumentService(DummyApiClient())
    expiries = ["2026-10-01", "2026-10-08", "2026-10-29"]
    today = date(2026, 9, 29)

    # Today is not in expiries -> PASS
    svc.verify_not_expiry_day(expiries, today=today)


def test_select_target_expiry():
    svc = UpstoxInstrumentService(DummyApiClient())
    expiries = ["2026-09-24", "2026-10-01", "2026-10-08", "2026-10-29"]
    today = date(2026, 9, 29)

    # Earliest future expiry strictly after today
    selected = svc.select_target_expiry(expiries, today=today)
    assert selected == "2026-10-01"


def test_select_target_expiry_fails_closed_when_no_future():
    svc = UpstoxInstrumentService(DummyApiClient())
    expiries = ["2026-09-22", "2026-09-24"]
    today = date(2026, 9, 29)

    with pytest.raises(ExpiryResolutionError, match="No future NIFTY expiry dates found"):
        svc.select_target_expiry(expiries, today=today)


def test_extract_expiries_from_contracts():
    svc = UpstoxInstrumentService(DummyApiClient())
    sample_contracts = [
        {"expiry": "2026-10-08T00:00:00", "strike_price": 23400},
        {"expiry": "2026-10-01", "strike_price": 23450},
        {"expiry": "2026-10-01", "strike_price": 23500},
        {"expiry": "2026-10-29", "strike_price": 23450},
    ]
    expiries = svc.get_expiry_dates(sample_contracts)
    assert expiries == ["2026-10-01", "2026-10-08", "2026-10-29"]
