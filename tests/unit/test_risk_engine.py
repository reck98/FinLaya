"""Unit tests for the pre-trade risk engine."""

import time
import pytest
from finlaya.execution.base import PaperPosition, PositionSide
from finlaya.market.state import InstrumentQuote, MarketDataCache
from finlaya.risk.risk_engine import RiskEngine, RiskViolationError


def test_risk_single_lot_enforcement():
    risk = RiskEngine(max_lots=1, lot_size=65)

    # 1 lot (65 qty) into FLAT -> valid
    pos_flat = PaperPosition(side=PositionSide.FLAT, quantity=0)
    risk.validate_pre_order(pos_flat, incoming_quantity=65, is_closing=False)

    # 2 lots (130 qty) into FLAT -> MUST raise RiskViolationError
    with pytest.raises(RiskViolationError, match="exceeds maximum allowed"):
        risk.validate_pre_order(pos_flat, incoming_quantity=130, is_closing=False)


def test_risk_no_pyramiding_or_multi_leg():
    risk = RiskEngine(max_lots=1, lot_size=65)

    # Already holding LONG_CE
    pos_ce = PaperPosition(side=PositionSide.LONG_CE, quantity=65, entry_price=100.0)

    # Attempting to add another position when not closing -> MUST raise RiskViolationError
    with pytest.raises(RiskViolationError, match="Position already open"):
        risk.validate_pre_order(pos_ce, incoming_quantity=65, is_closing=False)

    # Closing existing position -> allowed
    risk.validate_pre_order(pos_ce, incoming_quantity=65, is_closing=True)


def test_risk_data_staleness_check():
    risk = RiskEngine(max_staleness_seconds=2.0)
    cache = MarketDataCache()

    key = "NSE_INDEX|Nifty 50"
    # Fresh quote
    cache.update_quote(InstrumentQuote(instrument_key=key, ltp=23450.0, updated_at=time.monotonic()))
    assert risk.check_market_data_freshness(cache, [key]) is True

    # Stale quote (3.0s ago)
    cache.update_quote(InstrumentQuote(instrument_key=key, ltp=23450.0, updated_at=time.monotonic() - 3.0))
    assert risk.check_market_data_freshness(cache, [key]) is False
