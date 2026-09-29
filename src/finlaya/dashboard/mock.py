"""Mock event generator for development and visual UI testing."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

from .state import DashboardStateManager
from .websocket import WebSocketManager
from finlaya.utils.time import now_ist

logger = logging.getLogger(__name__)


class MockEventGenerator:
    """Generates synthetic high-frequency trading telemetry for UI verification."""

    def __init__(self, state_manager: DashboardStateManager, ws_manager: WebSocketManager):
        self.state_manager = state_manager
        self.ws_manager = ws_manager
        self._running = False
        self._task: asyncio.Task | None = None

        # Simulation parameters
        self.spot = 23456.20
        self.strike = 23450
        self.lot_size = 65
        self.ce_symbol = f"NIFTY26OCT{self.strike}CE"
        self.pe_symbol = f"NIFTY26OCT{self.strike}PE"
        self.ce_price = 142.50
        self.pe_price = 118.20
        self.position_side = "FLAT"
        self.entry_price = 0.0
        self.realized_pnl = 0.0
        self.order_counter = 100

    async def start(self) -> None:
        """Start synthetic generation loop."""
        self._running = True
        self.state_manager.is_mock = True
        self.state_manager.health["is_mock"] = True
        self.state_manager.health["bot_status"] = "RUNNING"
        self.state_manager.health["market_data_status"] = "LIVE"
        self.state_manager.health["laya_status"] = "READY"

        self.state_manager.session.update({
            "id": 999,
            "status": "ACTIVE",
            "trading_date": now_ist().strftime("%Y-%m-%d"),
            "started_at": now_ist().strftime("%Y-%m-%dT09:27:00+05:30"),
            "selected_strike": self.strike,
            "expiry": "2026-10-01",
            "lot_size": self.lot_size,
            "nifty_spot_at_start": 23450.00,
        })

        self._task = asyncio.create_task(self._run_loop())
        logger.info("Mock event generator started.")

    async def _run_loop(self) -> None:
        tick_count = 0

        while self._running:
            tick_count += 1
            now_iso = now_ist().isoformat()

            # 1. Market Tick Update (every 0.5s)
            spot_delta = round(random.gauss(0, 1.2), 2)
            self.spot = round(self.spot + spot_delta, 2)
            self.ce_price = max(1.0, round(self.ce_price + (spot_delta * 0.55), 2))
            self.pe_price = max(1.0, round(self.pe_price - (spot_delta * 0.50), 2))

            market_data = {
                "nifty_spot": self.spot,
                "ce_ltp": self.ce_price,
                "pe_ltp": self.pe_price,
                "ce_bid": round(self.ce_price - 0.10, 2),
                "ce_ask": round(self.ce_price + 0.10, 2),
                "pe_bid": round(self.pe_price - 0.10, 2),
                "pe_ask": round(self.pe_price + 0.10, 2),
                "ce_volume": 1234500 + tick_count * 15,
                "pe_volume": 1023400 + tick_count * 12,
                "ce_oi": 8765400,
                "pe_oi": 7654300,
                "timestamp": now_iso,
            }
            self.state_manager.apply_event("market_update", market_data)
            await self.ws_manager.broadcast({"type": "market_update", "data": market_data})

            # 2. Laya Decision Model Simulation (every 0.5s)
            latency_ms = round(random.uniform(140.0, 220.0), 1)

            if self.position_side == "FLAT":
                options = ["BUY", "SELL"]
                action = random.choices(["BUY", "SELL"], weights=[0.5, 0.5])[0]
                confidence = round(random.uniform(0.58, 0.88), 4)
            else:
                options = ["BUY", "SELL", "HOLD"]
                # Biased towards HOLD
                action = random.choices(["BUY", "SELL", "HOLD"], weights=[0.15, 0.15, 0.70])[0]
                confidence = round(random.uniform(0.60, 0.82), 4)

            accepted = confidence >= 0.60
            result = "HOLD POSITION"
            pos_before = self.position_side

            # State transition if accepted
            if accepted:
                if self.position_side == "FLAT":
                    if action == "BUY":
                        self.position_side = "LONG_CE"
                        self.entry_price = self.ce_price
                        result = "OPENED_CE"
                        await self._emit_order(self.ce_symbol, "BUY", self.ce_price)
                    elif action == "SELL":
                        self.position_side = "LONG_PE"
                        self.entry_price = self.pe_price
                        result = "OPENED_PE"
                        await self._emit_order(self.pe_symbol, "BUY", self.pe_price)
                elif self.position_side == "LONG_CE" and action == "SELL":
                    trade_pnl = (self.ce_price - self.entry_price) * self.lot_size
                    self.realized_pnl += trade_pnl
                    await self._emit_order(self.ce_symbol, "SELL", self.ce_price, trade_pnl)
                    self.position_side = "LONG_PE"
                    self.entry_price = self.pe_price
                    result = "SWITCH → PE"
                    await self._emit_order(self.pe_symbol, "BUY", self.pe_price)
                elif self.position_side == "LONG_PE" and action == "BUY":
                    trade_pnl = (self.pe_price - self.entry_price) * self.lot_size
                    self.realized_pnl += trade_pnl
                    await self._emit_order(self.pe_symbol, "SELL", self.pe_price, trade_pnl)
                    self.position_side = "LONG_CE"
                    self.entry_price = self.ce_price
                    result = "SWITCH → CE"
                    await self._emit_order(self.ce_symbol, "BUY", self.ce_price)

            decision_data = {
                "session_id": 999,
                "action": action,
                "confidence": confidence,
                "position_before": pos_before,
                "position_after": self.position_side,
                "question_options": options,
                "inference_latency_ms": latency_ms,
                "accepted": accepted,
                "result": result,
                "timestamp": now_iso,
            }
            self.state_manager.apply_event("laya_decision", decision_data)
            await self.ws_manager.broadcast({"type": "laya_decision", "data": decision_data})

            # 3. Position and P&L Update
            current_price = 0.0
            unrealized_pnl = 0.0
            instrument = None

            if self.position_side == "LONG_CE":
                instrument = self.ce_symbol
                current_price = self.ce_price
                unrealized_pnl = round((self.ce_price - self.entry_price) * self.lot_size, 2)
            elif self.position_side == "LONG_PE":
                instrument = self.pe_symbol
                current_price = self.pe_price
                unrealized_pnl = round((self.pe_price - self.entry_price) * self.lot_size, 2)

            pos_data = {
                "session_id": 999,
                "instrument": instrument,
                "side": self.position_side,
                "quantity": self.lot_size if self.position_side != "FLAT" else 0,
                "entry_price": self.entry_price,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": round(self.realized_pnl, 2),
                "total_pnl": round(self.realized_pnl + unrealized_pnl, 2),
                "timestamp": now_iso,
            }
            self.state_manager.apply_event("position_update", pos_data)
            await self.ws_manager.broadcast({"type": "position_update", "data": pos_data})

            # Heartbeat every cycle
            self.state_manager.health["last_heartbeat_time"] = time.monotonic()
            self.state_manager.health["last_heartbeat_iso"] = now_iso

            await asyncio.sleep(0.5)

    async def _emit_order(
        self, symbol: str, side: str, price: float, pnl: float | None = None
    ) -> None:
        self.order_counter += 1
        now_iso = now_ist().isoformat()
        order_data = {
            "order_id": self.order_counter,
            "session_id": 999,
            "instrument": symbol,
            "side": side,
            "quantity": self.lot_size,
            "fill_price": price,
            "status": "FILLED",
            "source": "SIM_QUOTE",
            "realized_pnl": pnl,
            "timestamp": now_iso,
        }
        self.state_manager.apply_event("order_update", order_data)
        await self.ws_manager.broadcast({"type": "order_update", "data": order_data})

        event_data = {
            "timestamp": now_iso,
            "level": "INFO",
            "event_type": "ORDER_FILLED",
            "message": f"Paper order #{self.order_counter} FILLED: {side} {self.lot_size}x {symbol} @ {price:.2f}",
        }
        self.state_manager.apply_event("event_log", event_data)
        await self.ws_manager.broadcast({"type": "event_log", "data": event_data})

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
