"""End-to-end integration test simulating a full FinLaya trading session."""

import pytest
from finlaya.config.settings import AppConfig, load_config
from finlaya.database.models import TradingSessionRecord
from finlaya.database.repository import SqliteRepository
from finlaya.execution.base import PositionSide
from finlaya.execution.order_manager import AtomicOrderManager
from finlaya.execution.paper_broker import PaperBroker
from finlaya.laya.model import MockDecisionModel
from finlaya.market.candles import Candle, CandleEngine
from finlaya.market.feature_engine import FeatureEngine
from finlaya.market.state import InstrumentQuote, MarketDataCache
from finlaya.risk.risk_engine import RiskEngine
from finlaya.scheduler.trading_clock import TradingClock
from finlaya.strategy.state_machine import StrategyState
from finlaya.strategy.strategy import FinLayaStrategy
from finlaya.utils.time import now_ist


@pytest.mark.asyncio
async def test_end_to_end_paper_trading_session(temp_db_repo: SqliteRepository, test_config: AppConfig):
    repo = temp_db_repo
    nifty_key = "NSE_INDEX|Nifty 50"
    ce_key = "NSE_FO|NIFTY26OCT23450CE"
    pe_key = "NSE_FO|NIFTY26OCT23450PE"
    ce_symbol = "NIFTY26OCT23450CE"
    pe_symbol = "NIFTY26OCT23450PE"

    # 1. Create Trading Session in SQLite
    session_id = await repo.create_session(
        TradingSessionRecord(
            trading_date=now_ist().strftime("%Y-%m-%d"),
            started_at=now_ist().isoformat(),
            status="ACTIVE",
            nifty_spot_at_start=23456.2,
            selected_strike=23450,
            expiry="2026-10-01",
            ce_instrument_key=ce_key,
            pe_instrument_key=pe_key,
            lot_size=65,
        )
    )
    assert session_id > 0

    # 2. Setup Market Data Cache
    cache = MarketDataCache()
    cache.update_quote(InstrumentQuote(instrument_key=nifty_key, ltp=23456.0, volume=1000000))
    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=150.0, bid=149.5, ask=150.5, volume=20000))
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=120.0, bid=119.5, ask=120.5, volume=18000))

    # 3. Setup Candle Engine
    candle_engine = CandleEngine(max_candles=6)
    candle_engine.seed_historical_candles(
        [
            Candle(timestamp=f"2026-09-29T09:2{i}:00+05:30", open=23450.0, high=23460.0, low=23440.0, close=23455.0, volume=5000)
            for i in range(6)
        ]
    )

    # 4. Feature Engine
    feature_engine = FeatureEngine(
        strike=23450,
        expiry="2026-10-01",
        ce_key=ce_key,
        ce_symbol=ce_symbol,
        pe_key=pe_key,
        pe_symbol=pe_symbol,
    )

    # 5. Mock Decision Model with Scripted Decisions
    model = MockDecisionModel()
    model.load()
    model.set_scripted_responses([
        ("BUY", 0.75),   # Step 1: Initial signal -> OPEN_LONG_CE
        ("HOLD", 0.80),  # Step 2: Maintain LONG_CE
        ("BUY", 0.70),   # Step 3: Maintain LONG_CE
        ("SELL", 0.72),  # Step 4: Reversal -> Switch LONG_CE -> FLAT -> LONG_PE
        ("HOLD", 0.65),  # Step 5: Maintain LONG_PE
    ])

    # 6. Execution Broker & Order Manager
    broker = PaperBroker(cache=cache, ce_key=ce_key, pe_key=pe_key, repository=repo)
    order_mgr = AtomicOrderManager(
        broker=broker,
        ce_key=ce_key,
        ce_symbol=ce_symbol,
        pe_key=pe_key,
        pe_symbol=pe_symbol,
        lot_size=65,
        num_lots=1,
    )

    risk_engine = RiskEngine(max_lots=1, lot_size=65, max_staleness_seconds=2.0)
    trading_clock = TradingClock(start_time_str="09:27:00", force_exit_time_str="15:13:00")

    strategy = FinLayaStrategy(
        session_id=session_id,
        config=test_config,
        cache=cache,
        candle_engine=candle_engine,
        feature_engine=feature_engine,
        model=model,
        broker=broker,
        order_manager=order_mgr,
        risk_engine=risk_engine,
        trading_clock=trading_clock,
        nifty_key=nifty_key,
        repository=repo,
    )

    # Step 1: Ingest tick 1 -> BUY 0.75 -> Enter LONG_CE
    await strategy.run_step()
    assert strategy.fsm.current_state == StrategyState.LONG_CE
    pos1 = broker.get_position()
    assert pos1.side == PositionSide.LONG_CE
    assert pos1.quantity == 65
    assert pos1.entry_price == 150.5  # filled at ask

    # Step 2: Ingest tick 2 -> HOLD 0.80 -> Stay LONG_CE
    await strategy.run_step()
    assert strategy.fsm.current_state == StrategyState.LONG_CE
    assert broker.get_position().quantity == 65

    # Step 3: Ingest tick 3 -> BUY 0.70 -> Stay LONG_CE
    await strategy.run_step()
    assert strategy.fsm.current_state == StrategyState.LONG_CE
    assert broker.get_position().quantity == 65

    # Update PE quote for switch: PE bid=119.5, ask=120.5; CE bid=155.0, ask=156.0
    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=155.5, bid=155.0, ask=156.0))
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=120.0, bid=119.5, ask=120.5))

    # Step 4: Ingest tick 4 -> SELL 0.72 -> Switch LONG_CE -> FLAT -> LONG_PE
    await strategy.run_step()
    assert strategy.fsm.current_state == StrategyState.LONG_PE
    pos4 = broker.get_position()
    assert pos4.side == PositionSide.LONG_PE
    assert pos4.quantity == 65
    assert pos4.entry_price == 120.5  # filled at ask
    # CE was exited at bid 155.0. Profit: (155.0 - 150.5) * 65 = 4.5 * 65 = 292.5
    assert pos4.realized_pnl == 292.5

    # Step 5: Ingest tick 5 -> HOLD 0.65 -> Stay LONG_PE
    await strategy.run_step()
    assert strategy.fsm.current_state == StrategyState.LONG_PE

    # Step 6: Trigger 15:13 Forced Exit
    # Update PE price to 125.0 (bid=124.5, ask=125.5)
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=125.0, bid=124.5, ask=125.5))
    await strategy.execute_forced_exit()

    # Final position MUST be verified FLAT
    final_pos = broker.get_position()
    assert final_pos.side == PositionSide.FLAT
    assert final_pos.quantity == 0
    # PE exit at bid 124.5: (124.5 - 120.5) * 65 = 4.0 * 65 = 260.0
    # Total Realized P&L = 292.5 + 260.0 = 552.5
    assert final_pos.realized_pnl == 552.5

    # 7. Verify SQLite Persistence & Research Stats
    stats = await repo.get_session_stats(session_id)
    assert stats["total_decisions"] == 5
    assert stats["buy_signals"] == 2
    assert stats["sell_signals"] == 1
    assert stats["hold_signals"] == 2
    assert stats["accepted_signals"] == 5
    assert stats["filled_orders"] == 4  # 1 buy CE, 1 sell CE, 1 buy PE, 1 sell PE (forced exit)
    assert stats["realized_pnl"] == 552.5
