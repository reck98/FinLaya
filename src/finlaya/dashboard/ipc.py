"""Asynchronous local UDP IPC receiver and heartbeat watchdog."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from .state import DashboardStateManager
from .websocket import WebSocketManager

logger = logging.getLogger(__name__)


class UDPProtocol(asyncio.DatagramProtocol):
    """AsyncIO Datagram Protocol for receiving telemetry packets."""

    def __init__(self, state_manager: DashboardStateManager, ws_manager: WebSocketManager):
        self.state_manager = state_manager
        self.ws_manager = ws_manager
        self.loop = asyncio.get_running_loop()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            payload = json.loads(data.decode("utf-8"))
            event_type = payload.get("type", "unknown")
            event_data = payload.get("data", {})

            # 1. Apply to in-memory state
            self.state_manager.apply_event(event_type, event_data)

            # 2. Broadcast to connected WebSockets
            self.loop.create_task(self.ws_manager.broadcast(payload))
        except Exception as e:
            logger.debug(f"Failed to process UDP datagram: {e}")

    def error_received(self, exc: Exception) -> None:
        logger.debug(f"UDP error received: {exc}")


class IPCReceiver:
    """Manages the UDP socket server and background liveness watchdog."""

    def __init__(
        self,
        state_manager: DashboardStateManager,
        ws_manager: WebSocketManager,
        host: str = "127.0.0.1",
        port: int = 8766,
        heartbeat_path: str = "data/runtime/heartbeat.json",
    ):
        self.state_manager = state_manager
        self.ws_manager = ws_manager
        self.host = host
        self.port = port
        self.heartbeat_path = Path(heartbeat_path)
        self.transport: asyncio.DatagramTransport | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start UDP server and watchdog task."""
        self._running = True
        loop = asyncio.get_running_loop()

        # 1. Start UDP server
        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(self.state_manager, self.ws_manager),
                local_addr=(self.host, self.port),
            )
            self.transport = transport
            logger.info(f"Telemetry UDP receiver listening on {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"Failed to bind UDP port {self.port}: {e}. Falling back to file polling.")

        # 2. Start Watchdog Task
        self._watchdog_task = asyncio.create_task(self._run_watchdog())

    async def _run_watchdog(self) -> None:
        """Periodic task to check heartbeat file and detect bot offline state."""
        prev_status = "WAITING"

        while self._running:
            try:
                # 1. Check runtime heartbeat file if UDP has not updated recently
                if self.heartbeat_path.exists():
                    try:
                        content = self.heartbeat_path.read_text(encoding="utf-8")
                        data = json.loads(content)
                        # Check timestamp in file
                        ts_str = data.get("timestamp")
                        status = data.get("status", "RUNNING")
                        session_id = data.get("session_id")
                        if session_id and not self.state_manager.session.get("id"):
                            self.state_manager.session["id"] = session_id
                    except Exception:
                        pass

                # 2. Check liveness threshold (3 seconds)
                is_alive = self.state_manager.check_liveness(timeout_seconds=3.0)
                current_status = self.state_manager.health["bot_status"]

                if current_status != prev_status:
                    prev_status = current_status
                    await self.ws_manager.broadcast({
                        "type": "system_status",
                        "data": self.state_manager.health,
                    })

            except Exception as e:
                logger.debug(f"Error in liveness watchdog: {e}")

            await asyncio.sleep(1.0)

    async def stop(self) -> None:
        """Stop receiver and cancel watchdog."""
        self._running = False
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
        if self.transport:
            self.transport.close()
