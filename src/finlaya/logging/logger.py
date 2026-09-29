"""Structured logging system with secret redaction and session tracing."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from finlaya.utils.time import IST, now_ist


class LogEvent(str, Enum):
    APPLICATION_START = "APPLICATION_START"
    UPSTOX_CONNECTED = "UPSTOX_CONNECTED"
    WEBSOCKET_CONNECTED = "WEBSOCKET_CONNECTED"
    MARKET_OPEN_CHECK = "MARKET_OPEN_CHECK"
    EXPIRY_CHECK = "EXPIRY_CHECK"
    EXPIRY_DAY_ABORT = "EXPIRY_DAY_ABORT"
    INSTRUMENT_SELECTION = "INSTRUMENT_SELECTION"
    STRIKE_SELECTED = "STRIKE_SELECTED"
    LOT_SIZE_VERIFIED = "LOT_SIZE_VERIFIED"
    LAYA_LOADED = "LAYA_LOADED"
    LAYA_INFERENCE = "LAYA_INFERENCE"
    SIGNAL_ACCEPTED = "SIGNAL_ACCEPTED"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_SWITCH_STARTED = "POSITION_SWITCH_STARTED"
    POSITION_SWITCH_COMPLETED = "POSITION_SWITCH_COMPLETED"
    STALE_MARKET_DATA = "STALE_MARKET_DATA"
    ORDER_FILLED = "ORDER_FILLED"
    FORCED_EXIT = "FORCED_EXIT"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    ERROR = "ERROR"


# Patterns to redact from logs
_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+"),
    re.compile(r"(access_token[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-\.]+([\"']?)", re.IGNORECASE),
    re.compile(r"(api_secret[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-\.]+([\"']?)", re.IGNORECASE),
    re.compile(r"(api_key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-\.]+([\"']?)", re.IGNORECASE),
    re.compile(r"(authorization[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-\.\s]+([\"']?)", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive credentials from any string."""
    result = text
    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(r"\1[REDACTED]\2" if r"\2" in pattern.pattern else r"\1[REDACTED]", result)
    return result


class SecretRedactingFormatter(logging.Formatter):
    """Logging formatter that strips credentials and produces clean text."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return redact_secrets(msg)


class JsonLinesFormatter(logging.Formatter):
    """Formats log records as structured JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": getattr(record, "ist_timestamp", now_ist().isoformat()),
            "level": record.levelname,
            "component": getattr(record, "component", record.name),
            "event": getattr(record, "event", "LOG"),
            "message": redact_secrets(record.getMessage()),
            "session_id": getattr(record, "session_id", None),
        }
        metadata = getattr(record, "metadata", None)
        if metadata:
            data["metadata"] = metadata
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


class FinLayaLogger:
    """Structured logger wrapper providing high-level event logging."""

    def __init__(self, name: str, session_id: int | None = None):
        self.name = name
        self._logger = logging.getLogger(name)
        self.session_id = session_id

    def set_session_id(self, session_id: int | None) -> None:
        self.session_id = session_id

    def log_event(
        self,
        event: LogEvent | str,
        message: str,
        level: int = logging.INFO,
        component: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event_str = event.value if isinstance(event, LogEvent) else str(event)
        extra = {
            "ist_timestamp": now_ist().isoformat(),
            "component": component or self.name,
            "event": event_str,
            "session_id": self.session_id,
            "metadata": metadata or {},
        }
        self._logger.log(level, f"[{event_str}] {message}", extra=extra)

    def info(self, message: str, event: LogEvent | str = "INFO", metadata: dict[str, Any] | None = None) -> None:
        self.log_event(event, message, level=logging.INFO, metadata=metadata)

    def warning(self, message: str, event: LogEvent | str = "WARNING", metadata: dict[str, Any] | None = None) -> None:
        self.log_event(event, message, level=logging.WARNING, metadata=metadata)

    def error(self, message: str, event: LogEvent | str = LogEvent.ERROR, metadata: dict[str, Any] | None = None, exc_info: bool = False) -> None:
        extra = {
            "ist_timestamp": now_ist().isoformat(),
            "component": self.name,
            "event": event.value if isinstance(event, LogEvent) else str(event),
            "session_id": self.session_id,
            "metadata": metadata or {},
        }
        self._logger.error(f"[{extra['event']}] {message}", extra=extra, exc_info=exc_info)

    def debug(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        self.log_event("DEBUG", message, level=logging.DEBUG, metadata=metadata)


_LOGGERS: dict[str, FinLayaLogger] = {}


def get_logger(name: str = "finlaya", session_id: int | None = None) -> FinLayaLogger:
    """Get or create a FinLayaLogger instance."""
    if name not in _LOGGERS:
        _LOGGERS[name] = FinLayaLogger(name, session_id=session_id)
    elif session_id is not None:
        _LOGGERS[name].set_session_id(session_id)
    return _LOGGERS[name]


def setup_logging(
    log_level: str = "INFO",
    log_dir: str | Path = "data/logs",
    console_enabled: bool = True,
) -> None:
    """Configure global root logging to console, log file, and JSON-lines file."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to prevent duplicate lines
    root.handlers.clear()

    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)

    # 1. Console Handler
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_fmt = SecretRedactingFormatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_fmt)
        root.addHandler(console_handler)

    # 2. Text File Handler
    log_file = path / f"finlaya_{now_ist().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_fmt = SecretRedactingFormatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    root.addHandler(file_handler)

    # 3. JSON Lines Handler
    json_file = path / f"finlaya_{now_ist().strftime('%Y%m%d')}.jsonl"
    json_handler = logging.FileHandler(json_file, encoding="utf-8")
    json_handler.setLevel(level)
    json_handler.setFormatter(JsonLinesFormatter())
    root.addHandler(json_handler)
