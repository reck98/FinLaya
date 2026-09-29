"""Integration tests for atomic position transitions and two-phase switching."""

import pytest
from finlaya.execution.base import OrderSide, OrderStatus, PositionSide
from finlaya.execution.order_manager import AtomicOrderManager
from finlaya.execution.paper_broker import PaperBroker
from finlaya.market.state import InstrumentQuote, MarketDataCache


@pytest.mark.asyncio
async def test_atomic_two_phase_switch_ce_to_pe():
    cache = MarketDataCache()
    ce_key = "NSE_FO|CE1"
    pe_key = "NSE_FO|PE1"

    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=100.0, bid=99.5, ask=100.5))
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=80.0, bid=79.5, ask=80.5))

    broker = PaperBroker(cache=cache, ce_key=ce_key, pe_key=pe_key)
    mgr = AtomicOrderManager(
        broker=broker,
        ce_key=ce_key,
        ce_symbol="NIFTY_CE",
        pe_key=pe_key,
        pe_symbol="NIFTY_PE",
        lot_size=65,
        num_lots=1,
    )

    # 1. Open initial LONG_CE
    opened = await mgr.open_from_flat(PositionSide.LONG_CE, session_id=1)
    assert opened is True
    assert broker.get_position().side == PositionSide.LONG_CE
    assert broker.get_position().quantity == 65
    assert broker.get_position().entry_price == 100.5

    # 2. Perform atomic switch: LONG_CE -> FLAT -> LONG_PE
    switched = await mgr.switch_ce_to_pe(session_id=1)
    assert switched is True

    # Verify final state is strictly LONG_PE with 65 qty
    final_pos = broker.get_position()
    assert final_pos.side == PositionSide.LONG_PE
    assert final_pos.quantity == 65
    assert final_pos.entry_price == 80.5
    # Realized P&L from CE exit at 99.5: (99.5 - 100.5) * 65 = -65.0
    assert final_pos.realized_pnl == -65.0


@pytest.mark.asyncio
async def test_atomic_two_phase_switch_pe_to_ce():
    cache = MarketDataCache()
    ce_key = "NSE_FO|CE1"
    pe_key = "NSE_FO|PE1"

    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=120.0, bid=119.5, ask=120.5))
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=90.0, bid=89.5, ask=90.5))

    broker = PaperBroker(cache=cache, ce_key=ce_key, pe_key=pe_key)
    mgr = AtomicOrderManager(
        broker=broker,
        ce_key=ce_key,
        ce_symbol="NIFTY_CE",
        pe_key=pe_key,
        pe_symbol="NIFTY_PE",
        lot_size=65,
        num_lots=1,
    )

    # 1. Open initial LONG_PE
    await mgr.open_from_flat(PositionSide.LONG_PE, session_id=1)
    assert broker.get_position().side == PositionSide.LONG_PE

    # 2. Switch LONG_PE -> FLAT -> LONG_CE
    switched = await mgr.switch_pe_to_ce(session_id=1)
    assert switched is True

    final_pos = broker.get_position()
    assert final_pos.side == PositionSide.LONG_CE
    assert final_pos.quantity == 65
    assert final_pos.entry_price == 120.5


@pytest.mark.asyncio
async def test_close_all_for_forced_exit():
    cache = MarketDataCache()
    ce_key = "NSE_FO|CE1"
    pe_key = "NSE_FO|PE1"

    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=150.0, bid=149.0, ask=151.0))
    broker = PaperBroker(cache=cache, ce_key=ce_key, pe_key=pe_key)
    mgr = AtomicOrderManager(
        broker=broker,
        ce_key=ce_key,
        ce_symbol="NIFTY_CE",
        pe_key=pe_key,
        pe_symbol="NIFTY_PE",
        lot_size=65,
        num_lots=1,
    )

    # Open LONG_CE
    await mgr.open_from_flat(PositionSide.LONG_CE, session_id=1)
    assert broker.get_position().side == PositionSide.LONG_CE

    # Trigger forced square-off
    closed = await mgr.close_all(session_id=1, reason="FORCED_EXIT")
    assert closed is True

    final_pos = broker.get_position()
    assert final_pos.side == PositionSide.FLAT
    assert final_pos.quantity == 0
