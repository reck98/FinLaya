"""Upstox Market Data Feeder V3 WebSocket client and cache updater."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any
import upstox_client

from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from finlaya.market.state import InstrumentQuote, MarketDataCache
from finlaya.utils.time import now_ist

logger = get_logger("upstox_market_data")


class UpstoxMarketDataFeed:
    """Manages Upstox MarketDataStreamerV3 WebSocket connection and updates MarketDataCache."""

    def __init__(self, api_client: upstox_client.ApiClient, cache: MarketDataCache):
        self.api_client = api_client
        self.cache = cache
        self.streamer: upstox_client.MarketDataStreamerV3 | None = None
        self._subscribed_keys: list[str] = []
        self._connected: bool = False
        self._thread: threading.Thread | None = None

    def is_connected(self) -> bool:
        return self._connected

    def subscribe(self, instrument_keys: list[str]) -> None:
        """Add new keys to stream."""
        for k in instrument_keys:
            if k not in self._subscribed_keys:
                self._subscribed_keys.append(k)
        if self.streamer and self._connected:
            self.streamer.subscribe(instrument_keys, "full")

    def unsubscribe(self, instrument_keys: list[str]) -> None:
        for k in instrument_keys:
            if k in self._subscribed_keys:
                self._subscribed_keys.remove(k)
        if self.streamer and self._connected:
            self.streamer.unsubscribe(instrument_keys)

    def _on_open(self) -> None:
        self._connected = True
        logger.info("Upstox Market Data WebSocket connected", LogEvent.WEBSOCKET_CONNECTED)

    def _on_close(self, ws: Any = None, close_status_code: Any = None, close_msg: Any = None) -> None:
        self._connected = False
        logger.warning(f"Upstox Market Data WebSocket disconnected (code={close_status_code}, msg={close_msg})")

    def _on_error(self, err: Any) -> None:
        logger.error(f"Upstox Market Data WebSocket error: {err}", LogEvent.ERROR)

    def _on_message(self, message: dict[str, Any]) -> None:
        """Handle incoming decoded protobuf payload from MarketDataStreamerV3."""
        try:
            feeds = message.get("feeds", {})
            if not isinstance(feeds, dict):
                return

            for key, feed_data in feeds.items():
                self._process_feed(key, feed_data)
        except Exception as e:
            logger.error(f"Error parsing market data feed message: {e}", LogEvent.ERROR)

    def _process_feed(self, instrument_key: str, feed: dict[str, Any]) -> None:
        full_feed = feed.get("fullFeed", {})
        ltpc = feed.get("ltpc", {})

        ltp = 0.0
        prev_close = None
        open_val = None
        high_val = None
        low_val = None
        close_val = None
        volume = 0
        oi = 0
        bid = None
        bid_qty = None
        ask = None
        ask_qty = None

        if "indexFF" in full_feed:
            idx = full_feed["indexFF"]
            idx_ltpc = idx.get("ltpc", {})
            ltp = float(idx_ltpc.get("ltp", 0.0))
            prev_close = float(idx_ltpc.get("cp", 0.0)) if "cp" in idx_ltpc else None
            ohlc_list = idx.get("marketOHLC", {}).get("ohlc", [])
            for o in ohlc_list:
                if o.get("interval") in ("1d", "1D", "I1"):
                    open_val = float(o.get("open", 0.0))
                    high_val = float(o.get("high", 0.0))
                    low_val = float(o.get("low", 0.0))
                    close_val = float(o.get("close", 0.0))
        elif "marketFF" in full_feed:
            mkt = full_feed["marketFF"]
            m_ltpc = mkt.get("ltpc", {})
            ltp = float(m_ltpc.get("ltp", 0.0))
            prev_close = float(m_ltpc.get("cp", 0.0)) if "cp" in m_ltpc else None
            volume = int(mkt.get("vtt", 0))
            oi = int(mkt.get("oi", 0))

            # Market depth level 1
            depth = mkt.get("marketLevel", {}).get("bidAskQuote", [])
            if depth and len(depth) > 0:
                best = depth[0]
                bid = float(best.get("bidPrice", 0.0)) or None
                bid_qty = int(best.get("bidQty", 0)) or None
                ask = float(best.get("askPrice", 0.0)) or None
                ask_qty = int(best.get("askQty", 0)) or None

            ohlc_list = mkt.get("marketOHLC", {}).get("ohlc", [])
            for o in ohlc_list:
                if o.get("interval") in ("1d", "1D", "I1"):
                    open_val = float(o.get("open", 0.0))
                    high_val = float(o.get("high", 0.0))
                    low_val = float(o.get("low", 0.0))
                    close_val = float(o.get("close", 0.0))
        elif ltpc:
            ltp = float(ltpc.get("ltp", 0.0))
            prev_close = float(ltpc.get("cp", 0.0)) if "cp" in ltpc else None

        if ltp <= 0.0:
            return

        day_change = (ltp - prev_close) if prev_close else None
        day_change_pct = (day_change / prev_close * 100.0) if prev_close and prev_close > 0 else None

        existing = self.cache.get_quote(instrument_key)
        oi_change = (oi - existing.oi) if existing and existing.oi > 0 else None

        quote = InstrumentQuote(
            instrument_key=instrument_key,
            ltp=ltp,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            prev_close=prev_close,
            day_change=round(day_change, 2) if day_change is not None else None,
            day_change_pct=round(day_change_pct, 4) if day_change_pct is not None else None,
            volume=volume,
            oi=oi,
            oi_change=oi_change,
            bid=bid,
            bid_qty=bid_qty,
            ask=ask,
            ask_qty=ask_qty,
            updated_at=time.monotonic(),
            ist_time=now_ist(),
        )
        self.cache.update_quote(quote)

    async def connect(self) -> None:
        """Establish WebSocket connection in background thread."""
        if not self._subscribed_keys:
            raise ValueError("No instrument keys configured to subscribe.")

        self.streamer = upstox_client.MarketDataStreamerV3(
            api_client=self.api_client,
            instrumentKeys=self._subscribed_keys,
            mode="full",
        )
        self.streamer.on("open", self._on_open)
        self.streamer.on("close", self._on_close)
        self.streamer.on("error", self._on_error)
        self.streamer.on("message", self._on_message)

        # Run connection in daemon thread to avoid blocking asyncio event loop
        self._thread = threading.Thread(target=self.streamer.connect, daemon=True)
        self._thread.start()

        # Wait briefly for open event
        for _ in range(50):
            if self._connected:
                break
            await asyncio.sleep(0.1)

    async def disconnect(self) -> None:
        """Disconnect WebSocket feed."""
        if self.streamer:
            try:
                self.streamer.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting streamer: {e}")
        self._connected = False
