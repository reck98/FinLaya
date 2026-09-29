"""Risk controls and safety guards for FinLaya."""

from __future__ import annotations

import logging
from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from finlaya.execution.base import PaperPosition, PositionSide
from finlaya.market.state import MarketDataCache

logger = get_logger("risk_engine")


class RiskViolationError(Exception):
    """Raised when a pre-trade or in-trade risk rule is breached."""


class RiskEngine:
    """Evaluates safety constraints before executing any paper order."""

    def __init__(
        self,
        max_lots: int = 1,
        lot_size: int = 65,
        max_staleness_seconds: float = 2.0,
    ):
        self.max_lots = max_lots
        self.lot_size = lot_size
        self.max_allowed_quantity = max_lots * lot_size
        self.max_staleness_seconds = max_staleness_seconds

    def check_market_data_freshness(self, cache: MarketDataCache, instrument_keys: list[str]) -> bool:
        """Verify market data is not stale."""
        for key in instrument_keys:
            if cache.is_stale(key, self.max_staleness_seconds):
                staleness = cache.get_staleness_seconds(key)
                logger.warning(
                    f"Market data stale for {key}: {staleness:.2f}s > {self.max_staleness_seconds}s. Rejecting decisions.",
                    LogEvent.STALE_MARKET_DATA,
                )
                return False
        return True

    def validate_pre_order(
        self,
        current_position: PaperPosition,
        incoming_quantity: int,
        is_closing: bool,
    ) -> None:
        """Validate pre-trade risk conditions."""
        if not is_closing:
            if current_position.side != PositionSide.FLAT and current_position.quantity > 0:
                raise RiskViolationError(
                    f"Position already open ({current_position.side.value}). Pyramiding and multiple legs are prohibited."
                )

            if incoming_quantity > self.max_allowed_quantity:
                raise RiskViolationError(
                    f"Order quantity {incoming_quantity} exceeds maximum allowed quantity {self.max_allowed_quantity} ({self.max_lots} lots)."
                )
