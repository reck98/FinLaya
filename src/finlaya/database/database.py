"""Async SQLite database connection manager and schema initialization."""

from __future__ import annotations

import logging
from pathlib import Path
import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trading_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trading_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,
    nifty_spot_at_start REAL,
    selected_strike INTEGER,
    expiry TEXT,
    ce_instrument_key TEXT,
    pe_instrument_key TEXT,
    lot_size INTEGER
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    nifty_spot REAL,
    ce_ltp REAL,
    pe_ltp REAL,
    ce_bid REAL,
    ce_ask REAL,
    pe_bid REAL,
    pe_ask REAL,
    ce_volume INTEGER,
    pe_volume INTEGER,
    ce_oi INTEGER,
    pe_oi INTEGER
);

CREATE TABLE IF NOT EXISTS laya_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    position_before TEXT NOT NULL,
    question_options TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence REAL NOT NULL,
    accepted INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    inference_latency_ms REAL NOT NULL,
    FOREIGN KEY(session_id) REFERENCES trading_sessions(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    instrument TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    order_type TEXT NOT NULL,
    requested_price REAL,
    fill_price REAL,
    status TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY(session_id) REFERENCES trading_sessions(id)
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    instrument TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    realized_pnl REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    FOREIGN KEY(session_id) REFERENCES trading_sessions(id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_time ON market_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_sess_time ON laya_decisions(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_orders_sess_time ON orders(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_positions_sess_time ON positions(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_sess_time ON events(timestamp);
"""


class DatabaseEngine:
    """Async SQLite database manager."""

    def __init__(self, db_path: str | Path = "data/finlaya.db"):
        self.db_path = Path(db_path)

    async def initialize(self) -> None:
        """Create database parent directories and run schema migrations."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA_SQL)
            # Enable WAL mode for concurrent reads/writes and performance
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")
            await db.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def connect(self) -> aiosqlite.Connection:
        """Return a direct async connection context."""
        return aiosqlite.connect(self.db_path)
