"""Repository for database operations and research telemetry querying."""

from __future__ import annotations

import json
from typing import Any, Protocol
import aiosqlite

from .models import (
    TradingSessionRecord,
    MarketSnapshotRecord,
    LayaDecisionRecord,
    OrderRecord,
    PositionRecord,
    EventRecord,
)


class DatabaseRepository(Protocol):
    async def create_session(self, session: TradingSessionRecord) -> int: ...
    async def update_session_status(self, session_id: int, status: str, ended_at: str | None = None) -> None: ...
    async def save_market_snapshot(self, snapshot: MarketSnapshotRecord) -> int: ...
    async def save_laya_decision(self, decision: LayaDecisionRecord) -> int: ...
    async def save_order(self, order: OrderRecord) -> int: ...
    async def update_order(self, order_id: int, status: str, fill_price: float | None = None, reason: str | None = None) -> None: ...
    async def save_position(self, position: PositionRecord) -> int: ...
    async def save_event(self, event: EventRecord) -> int: ...
    async def get_latest_session(self) -> TradingSessionRecord | None: ...
    async def get_session_stats(self, session_id: int) -> dict[str, Any]: ...


class SqliteRepository:
    """aiosqlite-backed repository for persistence and quantitative research retrieval."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def create_session(self, session: TradingSessionRecord) -> int:
        query = """
        INSERT INTO trading_sessions (
            trading_date, started_at, ended_at, status, nifty_spot_at_start,
            selected_strike, expiry, ce_instrument_key, pe_instrument_key, lot_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (
                    session.trading_date,
                    session.started_at,
                    session.ended_at,
                    session.status,
                    session.nifty_spot_at_start,
                    session.selected_strike,
                    session.expiry,
                    session.ce_instrument_key,
                    session.pe_instrument_key,
                    session.lot_size,
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def update_session_status(self, session_id: int, status: str, ended_at: str | None = None) -> None:
        query = "UPDATE trading_sessions SET status = ?, ended_at = COALESCE(?, ended_at) WHERE id = ?"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, (status, ended_at, session_id))
            await db.commit()

    async def save_market_snapshot(self, s: MarketSnapshotRecord) -> int:
        query = """
        INSERT INTO market_snapshots (
            timestamp, nifty_spot, ce_ltp, pe_ltp, ce_bid, ce_ask,
            pe_bid, pe_ask, ce_volume, pe_volume, ce_oi, pe_oi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (
                    s.timestamp, s.nifty_spot, s.ce_ltp, s.pe_ltp, s.ce_bid, s.ce_ask,
                    s.pe_bid, s.pe_ask, s.ce_volume, s.pe_volume, s.ce_oi, s.pe_oi,
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def save_laya_decision(self, d: LayaDecisionRecord) -> int:
        query = """
        INSERT INTO laya_decisions (
            session_id, timestamp, position_before, question_options,
            action, confidence, accepted, state_json, inference_latency_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (
                    d.session_id, d.timestamp, d.position_before, d.question_options,
                    d.action, d.confidence, d.accepted, d.state_json, d.inference_latency_ms,
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def save_order(self, o: OrderRecord) -> int:
        query = """
        INSERT INTO orders (
            session_id, timestamp, instrument, side, quantity,
            order_type, requested_price, fill_price, status, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (
                    o.session_id, o.timestamp, o.instrument, o.side, o.quantity,
                    o.order_type, o.requested_price, o.fill_price, o.status, o.reason,
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def update_order(self, order_id: int, status: str, fill_price: float | None = None, reason: str | None = None) -> None:
        query = "UPDATE orders SET status = ?, fill_price = COALESCE(?, fill_price), reason = COALESCE(?, reason) WHERE id = ?"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, (status, fill_price, reason, order_id))
            await db.commit()

    async def save_position(self, p: PositionRecord) -> int:
        query = """
        INSERT INTO positions (
            session_id, timestamp, instrument, side, quantity,
            entry_price, exit_price, realized_pnl, unrealized_pnl
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (
                    p.session_id, p.timestamp, p.instrument, p.side, p.quantity,
                    p.entry_price, p.exit_price, p.realized_pnl, p.unrealized_pnl,
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def save_event(self, e: EventRecord) -> int:
        query = """
        INSERT INTO events (timestamp, level, event_type, message, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (e.timestamp, e.level, e.event_type, e.message, e.metadata_json),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_latest_session(self) -> TradingSessionRecord | None:
        query = "SELECT * FROM trading_sessions ORDER BY id DESC LIMIT 1"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query) as cursor:
                row = await cursor.fetchone()
                if row:
                    return TradingSessionRecord(**dict(row))
        return None

    async def get_session_stats(self, session_id: int) -> dict[str, Any]:
        """Aggregate quantitative metrics for research."""
        stats: dict[str, Any] = {
            "session_id": session_id,
            "total_decisions": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "hold_signals": 0,
            "accepted_signals": 0,
            "avg_confidence": 0.0,
            "avg_latency_ms": 0.0,
            "total_orders": 0,
            "filled_orders": 0,
            "realized_pnl": 0.0,
        }
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Decisions
            async with db.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) as buys,
                    SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) as sells,
                    SUM(CASE WHEN action = 'HOLD' THEN 1 ELSE 0 END) as holds,
                    SUM(accepted) as accepted_cnt,
                    AVG(confidence) as avg_conf,
                    AVG(inference_latency_ms) as avg_lat
                FROM laya_decisions WHERE session_id = ?
                """,
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row["total"]:
                    stats["total_decisions"] = row["total"]
                    stats["buy_signals"] = row["buys"] or 0
                    stats["sell_signals"] = row["sells"] or 0
                    stats["hold_signals"] = row["holds"] or 0
                    stats["accepted_signals"] = row["accepted_cnt"] or 0
                    stats["avg_confidence"] = round(row["avg_conf"] or 0.0, 4)
                    stats["avg_latency_ms"] = round(row["avg_lat"] or 0.0, 2)

            # Orders
            async with db.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'FILLED' THEN 1 ELSE 0 END) as filled
                FROM orders WHERE session_id = ?
                """,
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats["total_orders"] = row["total"] or 0
                    stats["filled_orders"] = row["filled"] or 0

            # Latest PnL
            async with db.execute(
                "SELECT realized_pnl FROM positions WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats["realized_pnl"] = round(row["realized_pnl"], 2)

        return stats
