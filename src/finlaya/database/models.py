"""Data models for SQLite persistent tables."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class TradingSessionRecord(BaseModel):
    id: int | None = None
    trading_date: str
    started_at: str
    ended_at: str | None = None
    status: str
    nifty_spot_at_start: float | None = None
    selected_strike: int | None = None
    expiry: str | None = None
    ce_instrument_key: str | None = None
    pe_instrument_key: str | None = None
    lot_size: int | None = None


class MarketSnapshotRecord(BaseModel):
    id: int | None = None
    timestamp: str
    nifty_spot: float | None = None
    ce_ltp: float | None = None
    pe_ltp: float | None = None
    ce_bid: float | None = None
    ce_ask: float | None = None
    pe_bid: float | None = None
    pe_ask: float | None = None
    ce_volume: int | None = None
    pe_volume: int | None = None
    ce_oi: int | None = None
    pe_oi: int | None = None


class LayaDecisionRecord(BaseModel):
    id: int | None = None
    session_id: int
    timestamp: str
    position_before: str
    question_options: str
    action: str
    confidence: float
    accepted: int = 1
    state_json: str
    inference_latency_ms: float


class OrderRecord(BaseModel):
    id: int | None = None
    session_id: int
    timestamp: str
    instrument: str
    side: str
    quantity: int
    order_type: str = "MARKET"
    requested_price: float | None = None
    fill_price: float | None = None
    status: str
    reason: str | None = None


class PositionRecord(BaseModel):
    id: int | None = None
    session_id: int
    timestamp: str
    instrument: str
    side: str
    quantity: int
    entry_price: float
    exit_price: float | None = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0


class EventRecord(BaseModel):
    id: int | None = None
    timestamp: str
    level: str
    event_type: str
    message: str
    metadata_json: str | None = None
