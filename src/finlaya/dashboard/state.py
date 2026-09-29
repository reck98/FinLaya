"""In-memory thread-safe state store for real-time dashboard telemetry."""

from __future__ import annotations

import collections
import json
import logging
from pathlib import Path
import time
from typing import Any
import aiosqlite

from finlaya.utils.time import now_ist

logger = logging.getLogger(__name__)


class DashboardStateManager:
    """Maintains real-time telemetry state and recent history in memory."""

    def __init__(self, db_path: str = "data/finlaya.db", is_mock: bool = False):
        self.db_path = db_path
        self.is_mock = is_mock

        # Telemetry State
        self.session: dict[str, Any] = {
            "id": None,
            "status": "WAITING",
            "trading_date": now_ist().strftime("%Y-%m-%d"),
            "started_at": None,
            "selected_strike": None,
            "expiry": None,
            "lot_size": 65,
            "nifty_spot_at_start": None,
        }

        self.market: dict[str, Any] = {
            "nifty_spot": 0.0,
            "nifty_open": 0.0,
            "nifty_high": 0.0,
            "nifty_low": 0.0,
            "nifty_prev_close": 0.0,
            "ce_ltp": 0.0,
            "pe_ltp": 0.0,
            "ce_bid": 0.0,
            "ce_ask": 0.0,
            "pe_bid": 0.0,
            "pe_ask": 0.0,
            "ce_volume": 0,
            "pe_volume": 0,
            "ce_oi": 0,
            "pe_oi": 0,
            "timestamp": None,
            "updated_at": 0.0,  # monotonic timestamp
        }

        self.position: dict[str, Any] = {
            "side": "FLAT",
            "instrument": None,
            "quantity": 0,
            "entry_price": 0.0,
            "current_price": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "total_pnl": 0.0,
        }

        self.pnl: dict[str, Any] = {
            "realized": 0.0,
            "unrealized": 0.0,
            "total": 0.0,
            "history": [],  # list of {"timestamp": str, "pnl": float}
        }

        self.latest_decision: dict[str, Any] | None = None
        self.recent_decisions: collections.deque = collections.deque(maxlen=100)
        self.recent_orders: collections.deque = collections.deque(maxlen=50)
        self.recent_events: collections.deque = collections.deque(maxlen=100)

        self.stats: dict[str, Any] = {
            "laya_calls": 0,
            "buy_decisions": 0,
            "sell_decisions": 0,
            "hold_decisions": 0,
            "accepted_signals": 0,
            "position_switches": 0,
            "completed_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "avg_latency_ms": 0.0,
            "avg_confidence": 0.0,
        }

        self.health: dict[str, Any] = {
            "bot_status": "OFFLINE",
            "last_heartbeat_time": 0.0,  # monotonic
            "last_heartbeat_iso": None,
            "market_data_status": "WAITING",
            "laya_status": "WAITING",
            "database_status": "OK",
            "is_mock": is_mock,
        }

        self._prev_realized_pnl = 0.0

    async def hydrate_from_sqlite(self) -> None:
        """Hydrate state from SQLite on startup or page refresh."""
        if not Path(self.db_path).exists():
            return

        try:
            async with aiosqlite.connect(f"file:{self.db_path}?mode=ro", uri=True) as db:
                db.row_factory = aiosqlite.Row

                # 1. Latest Session
                async with db.execute("SELECT * FROM trading_sessions ORDER BY id DESC LIMIT 1") as cursor:
                    row = await cursor.fetchone()
                    if row:
                        self.session = dict(row)
                        if self.session.get("status") == "ACTIVE":
                            # Check if bot is really running or offline
                            pass

                # 2. Latest Position
                async with db.execute(
                    "SELECT * FROM positions ORDER BY id DESC LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        r = dict(row)
                        self.position = {
                            "side": r.get("side", "FLAT"),
                            "instrument": r.get("instrument"),
                            "quantity": r.get("quantity", 0),
                            "entry_price": r.get("entry_price", 0.0),
                            "current_price": r.get("entry_price", 0.0),
                            "unrealized_pnl": r.get("unrealized_pnl", 0.0),
                            "realized_pnl": r.get("realized_pnl", 0.0),
                            "total_pnl": round(r.get("realized_pnl", 0.0) + r.get("unrealized_pnl", 0.0), 2),
                        }
                        self.pnl["realized"] = self.position["realized_pnl"]
                        self.pnl["unrealized"] = self.position["unrealized_pnl"]
                        self.pnl["total"] = self.position["total_pnl"]

                # 3. Latest Market Snapshot
                async with db.execute("SELECT * FROM market_snapshots ORDER BY id DESC LIMIT 1") as cursor:
                    row = await cursor.fetchone()
                    if row:
                        r = dict(row)
                        self.market.update({
                            "nifty_spot": r.get("nifty_spot") or 0.0,
                            "ce_ltp": r.get("ce_ltp") or 0.0,
                            "pe_ltp": r.get("pe_ltp") or 0.0,
                            "ce_bid": r.get("ce_bid") or 0.0,
                            "ce_ask": r.get("ce_ask") or 0.0,
                            "pe_bid": r.get("pe_bid") or 0.0,
                            "pe_ask": r.get("pe_ask") or 0.0,
                            "ce_volume": r.get("ce_volume") or 0,
                            "pe_volume": r.get("pe_volume") or 0,
                            "ce_oi": r.get("ce_oi") or 0,
                            "pe_oi": r.get("pe_oi") or 0,
                            "timestamp": r.get("timestamp"),
                            "updated_at": time.monotonic(),
                        })

                # 4. Recent Decisions
                async with db.execute("SELECT * FROM laya_decisions ORDER BY id DESC LIMIT 50") as cursor:
                    rows = await cursor.fetchall()
                    for r in reversed(rows):
                        d = dict(r)
                        self.recent_decisions.appendleft(d)
                    if self.recent_decisions:
                        self.latest_decision = self.recent_decisions[0]

                # 5. Recent Orders
                async with db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 30") as cursor:
                    rows = await cursor.fetchall()
                    for r in rows:
                        self.recent_orders.append(dict(r))

                # 6. Recent Events
                async with db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 50") as cursor:
                    rows = await cursor.fetchall()
                    for r in rows:
                        self.recent_events.append(dict(r))

            self.health["database_status"] = "OK"
        except Exception as e:
            logger.warning(f"Error hydrating dashboard state from SQLite: {e}")
            self.health["database_status"] = "ERROR"

    def apply_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Apply live event to in-memory state."""
        now_mono = time.monotonic()

        if event_type == "heartbeat":
            self.health["bot_status"] = data.get("status", "RUNNING")
            self.health["last_heartbeat_time"] = now_mono
            self.health["last_heartbeat_iso"] = data.get("timestamp")
            if data.get("session_id") and not self.session.get("id"):
                self.session["id"] = data["session_id"]
            if data.get("metadata"):
                meta = data["metadata"]
                for k in ["selected_strike", "expiry", "lot_size"]:
                    if meta.get(k):
                        self.session[k] = meta[k]

        elif event_type == "market_update":
            data["updated_at"] = now_mono
            # Retain day high/low/open/prev close if spot moves
            spot = data.get("nifty_spot", 0.0)
            if spot > 0:
                if self.market["nifty_open"] == 0.0:
                    self.market["nifty_open"] = spot
                    self.market["nifty_high"] = spot
                    self.market["nifty_low"] = spot
                    self.market["nifty_prev_close"] = spot - 50.0  # reasonable baseline
                else:
                    self.market["nifty_high"] = max(self.market["nifty_high"], spot)
                    self.market["nifty_low"] = min(self.market["nifty_low"], spot)
            self.market.update(data)
            self.health["market_data_status"] = "LIVE"

        elif event_type == "laya_decision":
            data["received_at"] = now_mono
            self.latest_decision = data
            self.recent_decisions.appendleft(data)

            # Update stats
            self.stats["laya_calls"] += 1
            act = data.get("action", "")
            if act == "BUY":
                self.stats["buy_decisions"] += 1
            elif act == "SELL":
                self.stats["sell_decisions"] += 1
            elif act == "HOLD":
                self.stats["hold_decisions"] += 1

            if data.get("accepted"):
                self.stats["accepted_signals"] += 1
                if "SWITCH" in str(data.get("result", "")):
                    self.stats["position_switches"] += 1

            # Update running averages
            calls = self.stats["laya_calls"]
            conf = data.get("confidence", 0.0)
            lat = data.get("inference_latency_ms", 0.0)
            self.stats["avg_confidence"] = round(
                (self.stats["avg_confidence"] * (calls - 1) + conf) / calls, 4
            )
            self.stats["avg_latency_ms"] = round(
                (self.stats["avg_latency_ms"] * (calls - 1) + lat) / calls, 1
            )
            self.health["laya_status"] = "READY"

        elif event_type == "position_update":
            prev_realized = self.position.get("realized_pnl", 0.0)
            self.position.update(data)
            self.pnl["realized"] = data.get("realized_pnl", 0.0)
            self.pnl["unrealized"] = data.get("unrealized_pnl", 0.0)
            self.pnl["total"] = data.get("total_pnl", 0.0)

            # Check if a trade completed (realized PnL changed)
            new_realized = data.get("realized_pnl", 0.0)
            if new_realized != prev_realized:
                trade_pnl = new_realized - prev_realized
                self.stats["completed_trades"] += 1
                if trade_pnl > 0:
                    self.stats["winning_trades"] += 1
                else:
                    self.stats["losing_trades"] += 1
                if self.stats["completed_trades"] > 0:
                    self.stats["win_rate"] = round(
                        (self.stats["winning_trades"] / self.stats["completed_trades"]) * 100, 1
                    )

            # Append to intraday PnL history
            self.pnl["history"].append({
                "timestamp": data.get("timestamp") or now_ist().strftime("%H:%M:%S"),
                "pnl": self.pnl["total"],
            })
            if len(self.pnl["history"]) > 300:
                self.pnl["history"].pop(0)

        elif event_type == "order_update":
            self.recent_orders.appendleft(data)

        elif event_type == "pnl_update":
            self.pnl["realized"] = data.get("realized_pnl", self.pnl["realized"])
            self.pnl["unrealized"] = data.get("unrealized_pnl", 0.0)
            self.pnl["total"] = round(self.pnl["realized"] + self.pnl["unrealized"], 2)
            self.position["unrealized_pnl"] = self.pnl["unrealized"]
            self.position["total_pnl"] = self.pnl["total"]

        elif event_type == "event_log":
            self.recent_events.appendleft(data)

    def check_liveness(self, timeout_seconds: float = 3.0) -> bool:
        """Check if bot heartbeat has timed out."""
        if self.is_mock:
            self.health["bot_status"] = "RUNNING"
            return True

        if self.health["last_heartbeat_time"] == 0.0:
            self.health["bot_status"] = "OFFLINE"
            return False

        elapsed = time.monotonic() - self.health["last_heartbeat_time"]
        if elapsed > timeout_seconds:
            self.health["bot_status"] = "OFFLINE"
            return False
        return True

    def get_snapshot(self) -> dict[str, Any]:
        """Return complete snapshot for WebSocket hydration or REST polling."""
        return {
            "session": self.session,
            "market": self.market,
            "position": self.position,
            "pnl": self.pnl,
            "latest_decision": self.latest_decision,
            "recent_decisions": list(self.recent_decisions),
            "recent_orders": list(self.recent_orders),
            "recent_events": list(self.recent_events),
            "stats": self.stats,
            "health": {
                **self.health,
                "seconds_since_heartbeat": round(
                    time.monotonic() - self.health["last_heartbeat_time"], 1
                )
                if self.health["last_heartbeat_time"] > 0
                else None,
                "seconds_since_market": round(
                    time.monotonic() - self.market["updated_at"], 1
                )
                if self.market["updated_at"] > 0
                else None,
            },
        }
