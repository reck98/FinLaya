"""Feature engine to assemble structured decision snapshots for Laya."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from finlaya.utils.time import now_ist
from .candles import Candle
from .indicators import calculate_technical_indicators
from .state import InstrumentQuote, MarketDataCache


class SessionInfo(BaseModel):
    timestamp: str
    market_time: str
    position: str
    seconds_to_forced_exit: float


class UnderlyingState(BaseModel):
    symbol: str = "NIFTY"
    spot: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    volume: int | None = None


class ContractState(BaseModel):
    symbol: str
    instrument_key: str
    strike: int
    expiry: str
    ltp: float
    bid: float | None = None
    ask: float | None = None
    bid_qty: int | None = None
    ask_qty: int | None = None
    volume: int | None = None
    oi: int | None = None
    oi_change: int | None = None
    day_change: float | None = None
    day_change_pct: float | None = None


class SelectedContractsState(BaseModel):
    strike: int
    expiry: str
    ce: ContractState
    pe: ContractState


class PositionState(BaseModel):
    side: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float


class MarketStateSnapshot(BaseModel):
    session: SessionInfo
    underlying: UnderlyingState
    selected_contracts: SelectedContractsState
    position: PositionState
    candles_1m: list[Candle] = Field(default_factory=list)
    indicators: dict[str, float | None] = Field(default_factory=dict)

    def to_laya_json(self) -> str:
        """Produce deterministic JSON for Laya model ingestion."""
        return self.model_dump_json(indent=2)


class FeatureEngine:
    """Assembles frozen, consistent market state snapshots."""

    def __init__(self, strike: int, expiry: str, ce_key: str, ce_symbol: str, pe_key: str, pe_symbol: str):
        self.strike = strike
        self.expiry = expiry
        self.ce_key = ce_key
        self.ce_symbol = ce_symbol
        self.pe_key = pe_key
        self.pe_symbol = pe_symbol

    def build_snapshot(
        self,
        cache: MarketDataCache,
        nifty_key: str,
        current_position_side: str,
        current_quantity: int,
        entry_price: float,
        seconds_to_exit: float,
        candles: list[Candle],
        timestamp: datetime | None = None,
    ) -> MarketStateSnapshot:
        ts = timestamp or now_ist()
        nifty_q = cache.get_quote(nifty_key) or InstrumentQuote(instrument_key=nifty_key, ltp=0.0)
        ce_q = cache.get_quote(self.ce_key) or InstrumentQuote(instrument_key=self.ce_key, ltp=0.0)
        pe_q = cache.get_quote(self.pe_key) or InstrumentQuote(instrument_key=self.pe_key, ltp=0.0)

        # Current price and unrealized P&L
        curr_price = 0.0
        if current_position_side == "LONG_CE":
            curr_price = ce_q.ltp
        elif current_position_side == "LONG_PE":
            curr_price = pe_q.ltp

        unrealized_pnl = 0.0
        if current_position_side != "FLAT" and current_quantity > 0:
            unrealized_pnl = (curr_price - entry_price) * current_quantity

        indicators = calculate_technical_indicators(candles)

        return MarketStateSnapshot(
            session=SessionInfo(
                timestamp=ts.isoformat(),
                market_time=ts.strftime("%H:%M:%S"),
                position=current_position_side,
                seconds_to_forced_exit=max(0.0, seconds_to_exit),
            ),
            underlying=UnderlyingState(
                symbol="NIFTY",
                spot=nifty_q.ltp,
                open=nifty_q.open,
                high=nifty_q.high,
                low=nifty_q.low,
                prev_close=nifty_q.prev_close,
                day_change=nifty_q.day_change,
                day_change_pct=nifty_q.day_change_pct,
                volume=nifty_q.volume,
            ),
            selected_contracts=SelectedContractsState(
                strike=self.strike,
                expiry=self.expiry,
                ce=ContractState(
                    symbol=self.ce_symbol,
                    instrument_key=self.ce_key,
                    strike=self.strike,
                    expiry=self.expiry,
                    ltp=ce_q.ltp,
                    bid=ce_q.bid,
                    ask=ce_q.ask,
                    bid_qty=ce_q.bid_qty,
                    ask_qty=ce_q.ask_qty,
                    volume=ce_q.volume,
                    oi=ce_q.oi,
                    oi_change=ce_q.oi_change,
                    day_change=ce_q.day_change,
                    day_change_pct=ce_q.day_change_pct,
                ),
                pe=ContractState(
                    symbol=self.pe_symbol,
                    instrument_key=self.pe_key,
                    strike=self.strike,
                    expiry=self.expiry,
                    ltp=pe_q.ltp,
                    bid=pe_q.bid,
                    ask=pe_q.ask,
                    bid_qty=pe_q.bid_qty,
                    ask_qty=pe_q.ask_qty,
                    volume=pe_q.volume,
                    oi=pe_q.oi,
                    oi_change=pe_q.oi_change,
                    day_change=pe_q.day_change,
                    day_change_pct=pe_q.day_change_pct,
                ),
            ),
            position=PositionState(
                side=current_position_side,
                quantity=current_quantity,
                entry_price=entry_price,
                current_price=curr_price,
                unrealized_pnl=round(unrealized_pnl, 2),
            ),
            candles_1m=candles,
            indicators=indicators,
        )
