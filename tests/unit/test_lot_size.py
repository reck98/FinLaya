"""Unit tests for lot size validation and broker metadata verification."""

import pytest
from finlaya.broker.base import LotSizeMismatchError
from finlaya.broker.upstox_instruments import UpstoxInstrumentService
from finlaya.utils.validation import validate_lot_size


class DummyApiClient:
    pass


def test_validate_lot_size_matching():
    valid, msg = validate_lot_size(broker_lot_size=65, expected_lot_size=65, enforce=True)
    assert valid is True
    assert "matches expected" in msg


def test_validate_lot_size_mismatch_fails_safe():
    valid, msg = validate_lot_size(broker_lot_size=75, expected_lot_size=65, enforce=True)
    assert valid is False
    assert "Lot size mismatch" in msg
    assert "Aborting for safety" in msg


def test_validate_lot_size_enforce_disabled():
    valid, msg = validate_lot_size(broker_lot_size=75, expected_lot_size=65, enforce=False)
    assert valid is True
    assert "enforcement disabled" in msg


def test_discover_contracts_lot_size_enforcement():
    svc = UpstoxInstrumentService(DummyApiClient())
    contracts = [
        {
            "instrument_key": "NSE_FO|1",
            "trading_symbol": "NIFTY26OCT23450CE",
            "strike_price": 23450.0,
            "expiry": "2026-10-01",
            "instrument_type": "CE",
            "lot_size": 75,  # Changed by exchange from 65 to 75
        },
        {
            "instrument_key": "NSE_FO|2",
            "trading_symbol": "NIFTY26OCT23450PE",
            "strike_price": 23450.0,
            "expiry": "2026-10-01",
            "instrument_type": "PE",
            "lot_size": 75,
        },
    ]

    # When expected is 65 and enforce is True -> MUST raise LotSizeMismatchError
    with pytest.raises(LotSizeMismatchError, match="Broker reported 75, but configuration expected 65"):
        svc.discover_contracts(
            contracts=contracts,
            strike=23450,
            target_expiry="2026-10-01",
            expected_lot_size=65,
            enforce_lot_size=True,
        )

    # When expected is 75 -> PASS
    ce, pe = svc.discover_contracts(
        contracts=contracts,
        strike=23450,
        target_expiry="2026-10-01",
        expected_lot_size=75,
        enforce_lot_size=True,
    )
    assert ce.lot_size == 75
    assert pe.lot_size == 75
