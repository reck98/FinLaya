"""Atomic position transition manager with strict concurrency locks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from .base import OrderSide, OrderStatus, PaperOrder, PositionSide
from .paper_broker import PaperBroker

logger = get_logger("order_manager")


class TransitionError(Exception):
    """Raised when an atomic position transition encounters an unexpected fill or state error."""


class AtomicOrderManager:
    """Manages synchronized, atomic state transitions between option legs."""

    def __init__(
        self,
        broker: PaperBroker,
        ce_key: str,
        ce_symbol: str,
        pe_key: str,
        pe_symbol: str,
        lot_size: int,
        num_lots: int = 1,
    ):
        self.broker = broker
        self.ce_key = ce_key
        self.ce_symbol = ce_symbol
        self.pe_key = pe_key
        self.pe_symbol = pe_symbol
        self.lot_size = lot_size
        self.num_lots = num_lots
        self.order_quantity = lot_size * num_lots

        self._lock = asyncio.Lock()
        self._is_transitioning = False

    def is_busy(self) -> bool:
        """Check if an order transition is currently in progress."""
        return self._lock.locked() or self._is_transitioning

    async def open_from_flat(self, target_side: PositionSide, session_id: int) -> bool:
        """Open initial position from FLAT state (BUY CE or BUY PE)."""
        async with self._lock:
            self._is_transitioning = True
            try:
                curr = self.broker.get_position()
                if curr.side != PositionSide.FLAT:
                    logger.warning(f"Cannot open from FLAT: current position is already {curr.side.value}")
                    return False

                if target_side == PositionSide.LONG_CE:
                    order = await self.broker.submit_market_order(
                        instrument_key=self.ce_key,
                        symbol=self.ce_symbol,
                        side=OrderSide.BUY,
                        quantity=self.order_quantity,
                        session_id=session_id,
                    )
                elif target_side == PositionSide.LONG_PE:
                    order = await self.broker.submit_market_order(
                        instrument_key=self.pe_key,
                        symbol=self.pe_symbol,
                        side=OrderSide.BUY,
                        quantity=self.order_quantity,
                        session_id=session_id,
                    )
                else:
                    raise ValueError(f"Invalid target side for opening: {target_side}")

                if order.status != OrderStatus.FILLED:
                    raise TransitionError(f"Initial order failed to fill: status={order.status}, reason={order.reason}")

                after = self.broker.get_position()
                if after.side != target_side or after.quantity != self.order_quantity:
                    raise TransitionError(
                        f"Position verification failed: expected {target_side.value} ({self.order_quantity}), got {after.side.value} ({after.quantity})"
                    )

                return True
            finally:
                self._is_transitioning = False

    async def switch_ce_to_pe(self, session_id: int) -> bool:
        """Atomically transition LONG_CE -> FLAT -> LONG_PE."""
        async with self._lock:
            self._is_transitioning = True
            logger.info("Atomic position switch started: LONG_CE -> FLAT -> LONG_PE", LogEvent.POSITION_SWITCH_STARTED)
            try:
                curr = self.broker.get_position()
                if curr.side != PositionSide.LONG_CE:
                    logger.warning(f"Cannot switch CE->PE: current position is {curr.side.value}, not LONG_CE")
                    return False

                # Phase 1: Exit CE
                exit_order = await self.broker.submit_market_order(
                    instrument_key=self.ce_key,
                    symbol=self.ce_symbol,
                    side=OrderSide.SELL,
                    quantity=curr.quantity,
                    session_id=session_id,
                )
                if exit_order.status != OrderStatus.FILLED:
                    raise TransitionError(f"Phase 1 exit CE order failed to fill: {exit_order.reason}")

                # Verify FLAT
                mid_pos = self.broker.get_position()
                if mid_pos.side != PositionSide.FLAT or mid_pos.quantity != 0:
                    raise TransitionError(f"Phase 1 intermediate verification failed: position is {mid_pos.side.value} ({mid_pos.quantity})")

                # Phase 2: Enter PE
                enter_order = await self.broker.submit_market_order(
                    instrument_key=self.pe_key,
                    symbol=self.pe_symbol,
                    side=OrderSide.BUY,
                    quantity=self.order_quantity,
                    session_id=session_id,
                )
                if enter_order.status != OrderStatus.FILLED:
                    raise TransitionError(f"Phase 2 enter PE order failed to fill: {enter_order.reason}")

                # Verify LONG_PE
                final_pos = self.broker.get_position()
                if final_pos.side != PositionSide.LONG_PE or final_pos.quantity != self.order_quantity:
                    raise TransitionError(
                        f"Phase 2 final verification failed: position is {final_pos.side.value} ({final_pos.quantity})"
                    )

                logger.info("Atomic position switch completed: LONG_CE -> FLAT -> LONG_PE", LogEvent.POSITION_SWITCH_COMPLETED)
                return True
            finally:
                self._is_transitioning = False

    async def switch_pe_to_ce(self, session_id: int) -> bool:
        """Atomically transition LONG_PE -> FLAT -> LONG_CE."""
        async with self._lock:
            self._is_transitioning = True
            logger.info("Atomic position switch started: LONG_PE -> FLAT -> LONG_CE", LogEvent.POSITION_SWITCH_STARTED)
            try:
                curr = self.broker.get_position()
                if curr.side != PositionSide.LONG_PE:
                    logger.warning(f"Cannot switch PE->CE: current position is {curr.side.value}, not LONG_PE")
                    return False

                # Phase 1: Exit PE
                exit_order = await self.broker.submit_market_order(
                    instrument_key=self.pe_key,
                    symbol=self.pe_symbol,
                    side=OrderSide.SELL,
                    quantity=curr.quantity,
                    session_id=session_id,
                )
                if exit_order.status != OrderStatus.FILLED:
                    raise TransitionError(f"Phase 1 exit PE order failed to fill: {exit_order.reason}")

                # Verify FLAT
                mid_pos = self.broker.get_position()
                if mid_pos.side != PositionSide.FLAT or mid_pos.quantity != 0:
                    raise TransitionError(f"Phase 1 intermediate verification failed: position is {mid_pos.side.value} ({mid_pos.quantity})")

                # Phase 2: Enter CE
                enter_order = await self.broker.submit_market_order(
                    instrument_key=self.ce_key,
                    symbol=self.ce_symbol,
                    side=OrderSide.BUY,
                    quantity=self.order_quantity,
                    session_id=session_id,
                )
                if enter_order.status != OrderStatus.FILLED:
                    raise TransitionError(f"Phase 2 enter CE order failed to fill: {enter_order.reason}")

                # Verify LONG_CE
                final_pos = self.broker.get_position()
                if final_pos.side != PositionSide.LONG_CE or final_pos.quantity != self.order_quantity:
                    raise TransitionError(
                        f"Phase 2 final verification failed: position is {final_pos.side.value} ({final_pos.quantity})"
                    )

                logger.info("Atomic position switch completed: LONG_PE -> FLAT -> LONG_CE", LogEvent.POSITION_SWITCH_COMPLETED)
                return True
            finally:
                self._is_transitioning = False

    async def close_all(self, session_id: int, reason: str = "FORCED_EXIT") -> bool:
        """Close any open position and verify FLAT state."""
        async with self._lock:
            self._is_transitioning = True
            try:
                curr = self.broker.get_position()
                if curr.side == PositionSide.FLAT or curr.quantity == 0:
                    logger.info("Position is already FLAT. No orders needed for close_all.")
                    return True

                instrument_key = self.ce_key if curr.side == PositionSide.LONG_CE else self.pe_key
                symbol = self.ce_symbol if curr.side == PositionSide.LONG_CE else self.pe_symbol

                logger.info(f"Executing forced exit market order for {curr.side.value} ({curr.quantity} qty)", LogEvent.FORCED_EXIT)
                order = await self.broker.submit_market_order(
                    instrument_key=instrument_key,
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=curr.quantity,
                    session_id=session_id,
                )
                if order.status != OrderStatus.FILLED:
                    raise TransitionError(f"Forced exit order failed to fill: {order.reason}")

                after = self.broker.get_position()
                if after.side != PositionSide.FLAT or after.quantity != 0:
                    raise TransitionError(f"Forced exit position verification failed: position is {after.side.value} ({after.quantity})")

                logger.info("Verified position is strictly FLAT following forced exit.", LogEvent.FORCED_EXIT)
                return True
            finally:
                self._is_transitioning = False
