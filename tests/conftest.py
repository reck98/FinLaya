"""Global pytest fixtures and mock test doubles for FinLaya."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import AsyncGenerator
import pytest
import pytest_asyncio

from finlaya.config.settings import AppConfig, load_config
from finlaya.database.database import DatabaseEngine
from finlaya.database.repository import SqliteRepository
from finlaya.laya.model import MockDecisionModel
from finlaya.market.candles import Candle, CandleEngine
from finlaya.market.feature_engine import FeatureEngine
from finlaya.market.state import InstrumentQuote, MarketDataCache
from finlaya.execution.paper_broker import PaperBroker
from finlaya.execution.order_manager import AtomicOrderManager
from finlaya.risk.risk_engine import RiskEngine
from finlaya.scheduler.trading_clock import TradingClock


@pytest.fixture
def test_config() -> AppConfig:
    """Provide a standard AppConfig fixture with test defaults."""
    cfg = load_config()
    cfg.strategy.confidence_threshold = 0.60
    cfg.trading.lots = 1
    cfg.trading.expected_lot_size = 65
    cfg.trading.enforce_expected_lot_size = True
    cfg.trading.strike_step = 50
    return cfg


@pytest_asyncio.fixture
async def temp_db_repo() -> AsyncGenerator[SqliteRepository, None]:
    """Provide an initialized SQLite database in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_finlaya.db"
        engine = DatabaseEngine(db_path)
        await engine.initialize()
        repo = SqliteRepository(str(db_path))
        yield repo


@pytest.fixture
def market_cache() -> MarketDataCache:
    """Provide a market cache pre-seeded with live quotes."""
    cache = MarketDataCache()
    cache.update_quote(
        InstrumentQuote(
            instrument_key="NSE_INDEX|Nifty 50",
            ltp=23456.25,
            open=23400.0,
            high=23500.0,
            low=23380.0,
            prev_close=23400.0,
            day_change=56.25,
            day_change_pct=0.24,
            volume=5000000,
        )
    )
    cache.update_quote(
        InstrumentQuote(
            instrument_key="NSE_FO|NIFTY26OCT23450CE",
            ltp=152.4,
            bid=152.2,
            bid_qty=1300,
            ask=152.5,
            ask_qty=1950,
            volume=120000,
            oi=980000,
        )
    )
    cache.update_quote(
        InstrumentQuote(
            instrument_key="NSE_FO|NIFTY26OCT23450PE",
            ltp=118.1,
            bid=118.0,
            bid_qty=1100,
            ask=118.3,
            ask_qty=1625,
            volume=95000,
            oi=850000,
        )
    )
    return cache


@pytest.fixture
def mock_laya_model() -> MockDecisionModel:
    """Provide a loaded mock Laya model."""
    model = MockDecisionModel(default_action="BUY", default_confidence=0.72)
    model.load()
    return model


@pytest.fixture
def candle_engine_seeded() -> CandleEngine:
    """Provide a candle engine pre-seeded with 6 completed 1-minute candles."""
    engine = CandleEngine(max_candles=6)
    candles = [
        Candle(timestamp=f"2026-09-29T09:2{i}:00+05:30", open=23420.0 + i, high=23430.0 + i, low=23415.0 + i, close=23425.0 + i, volume=10000)
        for i in range(6)
    ]
    engine.seed_historical_candles(candles)
    return engine
