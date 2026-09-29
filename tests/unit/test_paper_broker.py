"""Unit tests for paper execution broker, fills, and P&L calculations."""

import pytest
from finlaya.execution.base import OrderSide, OrderStatus, PositionSide
from finlaya.execution.fills import calculate_fill_price
from finlaya.execution.paper_broker import PaperBroker
from finlaya.market.state import InstrumentQuote, MarketDataCache


def test_calculate_fill_price_bid_ask():
    # BUY fills at ask
    fill_buy, source_buy = calculate_fill_price(OrderSide.BUY, ask=155.0, bid=154.0, ltp=154.5)
    assert fill_buy == 155.0
    assert source_buy == "ask"

    # SELL fills at bid
    fill_sell, source_sell = calculate_fill_price(OrderSide.SELL, ask=155.0, bid=154.0, ltp=154.5)
    assert fill_sell == 154.0
    assert source_sell == "bid"


def test_calculate_fill_price_fallback():
    # BUY falls back to LTP when ask is None
    fill, source = calculate_fill_price(OrderSide.BUY, ask=None, bid=None, ltp=150.0, price_fallback="ltp")
    assert fill == 150.0
    assert source == "ltp_fallback"

    # SELL falls back to LTP when bid is None
    fill, source = calculate_fill_price(OrderSide.SELL, ask=None, bid=None, ltp=150.0, price_fallback="ltp")
    assert fill == 150.0
    assert source == "ltp_fallback"


@pytest.mark.asyncio
async def test_paper_broker_buy_and_sell_lifecycle():
    cache = MarketDataCache()
    ce_key = "NSE_FO|CE1"
    pe_key = "NSE_FO|PE1"

    # Populate cache
    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=100.0, bid=99.5, ask=100.5))
    broker = PaperBroker(cache=cache, ce_key=ce_key, pe_key=pe_key)

    assert broker.get_position().side == PositionSide.FLAT

    # 1. Submit market BUY order for 65 qty CE
    buy_order = await broker.submit_market_order(
        instrument_key=ce_key,
        symbol="NIFTY_CE",
        side=OrderSide.BUY,
        quantity=65,
        session_id=1,
    )

    assert buy_order.status == OrderStatus.FILLED
    assert buy_order.fill_price == 100.5  # Filled at ask
    assert buy_order.pricing_source == "ask"

    pos = broker.get_position()
    assert pos.side == PositionSide.LONG_CE
    assert pos.quantity == 65
    assert pos.entry_price == 100.5
    assert pos.realized_pnl == 0.0

    # 2. Market price increases to 110.0 (bid=109.5, ask=110.5)
    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=110.0, bid=109.5, ask=110.5))
    unrealized = broker.refresh_unrealized_pnl()
    # (110.0 - 100.5) * 65 = 9.5 * 65 = 617.5
    assert unrealized == 617.5

    # 3. Submit market SELL order to close CE position
    sell_order = await broker.submit_market_order(
        instrument_key=ce_key,
        symbol="NIFTY_CE",
        side=OrderSide.SELL,
        quantity=65,
        session_id=1,
    )

    assert sell_order.status == OrderStatus.FILLED
    assert sell_order.fill_price == 109.5  # Filled at bid
    assert sell_order.pricing_source == "bid"

    final_pos = broker.get_position()
    assert final_pos.side == PositionSide.FLAT
    assert final_pos.quantity == 0
    # Realized P&L = (109.5 - 100.5) * 65 = 9.0 * 65 = 585.0
    assert final_pos.realized_pnl == 585.0
    assert final_pos.unrealized_pnl == 0.0
