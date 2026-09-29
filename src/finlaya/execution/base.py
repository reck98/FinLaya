"""Execution data structures, order states, and broker protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(str, Enum):
    FLAT = "FLAT"
    LONG_CE = "LONG_CE"
    LONG_PE = "LONG_PE"


@dataclass
class PaperOrder:
    order_id: int
    session_id: int
    timestamp: str
    instrument_key: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: str = "MARKET"
    requested_price: float = 0.0
    fill_price: float = 0.0
    pricing_source: str = "ltp"
    status: OrderStatus = OrderStatus.PENDING
    reason: str | None = None


@dataclass
class PaperPosition:
    instrument_key: str | None = None
    symbol: str | None = None
    side: PositionSide = PositionSide.FLAT
    quantity: int = 0
    entry_price: float = 0.0
    current_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0


class ExecutionBroker(Protocol):
    """Abstract interface for local simulated execution or theoretical broker."""

    async def submit_market_order(
        self,
        instrument_key: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        session_id: int,
    ) -> PaperOrder: ...

    async def cancel_order(self, order_id: int) -> bool: ...
    def get_position(self) -> PaperPosition: ...
    def get_order(self, order_id: int) -> PaperOrder | None: ...
