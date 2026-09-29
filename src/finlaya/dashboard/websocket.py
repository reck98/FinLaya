"""WebSocket connection manager for real-time dashboard updates."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages active browser WebSocket connections and broadcasts telemetry updates."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, initial_snapshot: dict[str, Any] | None = None) -> None:
        """Accept new WebSocket connection and send initial hydration snapshot."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

        if initial_snapshot:
            try:
                await websocket.send_json({
                    "type": "snapshot",
                    "data": initial_snapshot,
                })
            except Exception as e:
                logger.warning(f"Failed to send initial snapshot to WebSocket client: {e}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove disconnected WebSocket client."""
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast JSON message to all active WebSocket clients."""
        if not self.active_connections:
            return

        dead_connections: list[WebSocket] = []
        payload_str = json.dumps(message, default=str)

        async with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_text(payload_str)
            except Exception:
                dead_connections.append(connection)

        if dead_connections:
            async with self._lock:
                for dead in dead_connections:
                    self.active_connections.discard(dead)
