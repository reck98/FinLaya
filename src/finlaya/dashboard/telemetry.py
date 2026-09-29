"""Telemetry broadcaster for emitting non-blocking real-time events to the dashboard."""

from __future__ import annotations

import json
import logging
import os
import socket
from pathlib import Path
from typing import Any

from finlaya.utils.time import now_ist

logger = logging.getLogger(__name__)

DEFAULT_TELEMETRY_PORT = 8766
DEFAULT_HEARTBEAT_PATH = "data/runtime/heartbeat.json"


class TelemetryBroadcaster:
    """Non-blocking local IPC broadcaster that transmits live trading telemetry.

    Uses UDP loopback (127.0.0.1) for microsecond-latency event emission without blocking
    the 0.5s quantitative strategy loop. Also manages the persistent heartbeat file.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = DEFAULT_TELEMETRY_PORT,
        heartbeat_path: str | Path = DEFAULT_HEARTBEAT_PATH,
    ):
        self.host = host
        self.port = port
        self.heartbeat_path = Path(heartbeat_path)
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        self._sock: socket.socket | None = None
        self._init_socket()

    def _init_socket(self) -> None:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setblocking(False)
        except Exception as e:
            logger.warning(f"Failed to initialize telemetry UDP socket: {e}")
            self._sock = None

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Send a JSON payload over UDP. Never raises or blocks."""
        if not self._sock:
            return

        payload = {
            "type": event_type,
            "timestamp": now_ist().isoformat(),
            "data": data,
        }
        try:
            raw = json.dumps(payload, default=str).encode("utf-8")
            self._sock.sendto(raw, (self.host, self.port))
        except Exception:
            # Drop silently if destination unreachable or buffer full
            pass

    def record_heartbeat(
        self,
        session_id: int | None = None,
        status: str = "RUNNING",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update heartbeat file and emit heartbeat event."""
        now_str = now_ist().isoformat()
        heartbeat_data = {
            "pid": os.getpid(),
            "session_id": session_id,
            "status": status,
            "timestamp": now_str,
            "metadata": metadata or {},
        }

        # 1. Emit over UDP
        self.emit("heartbeat", heartbeat_data)

        # 2. Write to runtime file
        try:
            tmp_path = self.heartbeat_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(heartbeat_data, indent=2), encoding="utf-8")
            tmp_path.replace(self.heartbeat_path)
        except Exception as e:
            logger.debug(f"Failed to write heartbeat file: {e}")

    def close(self) -> None:
        """Close the underlying UDP socket."""
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
