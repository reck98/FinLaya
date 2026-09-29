"""Run a simulated paper-trading session with mock market data and mock Laya decisions."""

import asyncio
from finlaya.config.settings import load_config
from finlaya.database.database import DatabaseEngine
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
from finlaya.strategy.strategy import FinLayaStrategy
from finlaya.utils.time import now_ist


async def main():
    print("=" * 60)
    print("Running FinLaya End-to-End Simulation")
    print("=" * 60)

    config = load_config()
    db_engine = DatabaseEngine(config.database.path)
    await db_engine.initialize()
    repo = SqliteRepository(config.database.path)

    nifty_key = "NSE_INDEX|Nifty 50"
    ce_key = "NSE_FO|NIFTY26OCT23450CE"
    pe_key = "NSE_FO|NIFTY26OCT23450PE"
    ce_symbol = "NIFTY26OCT23450CE"
    pe_symbol = "NIFTY26OCT23450PE"

    session_id = await repo.create_session(
        TradingSessionRecord(
            trading_date=now_ist().strftime("%Y-%m-%d"),
            started_at=now_ist().isoformat(),
            status="ACTIVE",
            nifty_spot_at_start=23456.25,
            selected_strike=23450,
            expiry="2026-10-01",
            ce_instrument_key=ce_key,
            pe_instrument_key=pe_key,
            lot_size=65,
        )
    )
    print(f"Created simulation session #{session_id}")

    cache = MarketDataCache()
    cache.update_quote(InstrumentQuote(instrument_key=nifty_key, ltp=23456.25, volume=5000000))
    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=152.0, bid=151.5, ask=152.5, volume=120000, oi=980000))
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=118.0, bid=117.5, ask=118.5, volume=95000, oi=850000))

    candle_engine = CandleEngine(max_candles=6)
    candle_engine.seed_historical_candles(
        [
            Candle(timestamp=f"2026-09-29T09:2{i}:00+05:30", open=23450.0 + i, high=23460.0 + i, low=23440.0 + i, close=23455.0 + i, volume=5000)
            for i in range(6)
        ]
    )

    feature_engine = FeatureEngine(
        strike=23450,
        expiry="2026-10-01",
        ce_key=ce_key,
        ce_symbol=ce_symbol,
        pe_key=pe_key,
        pe_symbol=pe_symbol,
    )

    model = MockDecisionModel()
    model.load()
    model.set_scripted_responses([
        ("BUY", 0.76),   # 1. Enters LONG_CE
        ("HOLD", 0.82),  # 2. Holds LONG_CE
        ("BUY", 0.68),   # 3. Holds LONG_CE
        ("SELL", 0.74),  # 4. Swaps to LONG_PE (via FLAT)
        ("HOLD", 0.65),  # 5. Holds LONG_PE
    ])

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
        config=config,
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

    # Tick 1: BUY -> opens LONG_CE
    print("Tick 1: Generating decision...")
    await strategy.run_step()
    print(f"  Position: {broker.get_position().side.value}, Qty: {broker.get_position().quantity}, Entry: {broker.get_position().entry_price}")

    # Tick 2: HOLD -> remains LONG_CE
    print("Tick 2: Generating decision...")
    await strategy.run_step()

    # Tick 3: Price rises
    print("Tick 3: Market price rises...")
    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=160.0, bid=159.5, ask=160.5))
    await strategy.run_step()

    # Tick 4: SELL -> atomic switch to LONG_PE
    print("Tick 4: Reversal signal SELL -> switching to LONG_PE...")
    cache.update_quote(InstrumentQuote(instrument_key=ce_key, ltp=162.0, bid=161.5, ask=162.5))
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=115.0, bid=114.5, ask=115.5))
    await strategy.run_step()
    print(f"  Position: {broker.get_position().side.value}, Qty: {broker.get_position().quantity}, Entry: {broker.get_position().entry_price}")

    # Tick 5: HOLD -> remains LONG_PE
    print("Tick 5: Generating decision...")
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=122.0, bid=121.5, ask=122.5))
    await strategy.run_step()

    # Tick 6: 15:13 Forced exit
    print("Tick 6: Executing 15:13 forced exit...")
    cache.update_quote(InstrumentQuote(instrument_key=pe_key, ltp=125.0, bid=124.5, ask=125.5))
    await strategy.execute_forced_exit()

    final_pos = broker.get_position()
    print(f"Final Position: {final_pos.side.value}, Realized P&L = {final_pos.realized_pnl:+.2f}")
    print("=" * 60)
    print("Simulation completed successfully. Database populated.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
