"""Simulated local paper execution broker with explicit order states."""

from __future__ import annotations

import logging
from typing import Any
from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from finlaya.market.state import MarketDataCache
from finlaya.utils.time import now_ist
from finlaya.database.models import OrderRecord, PositionRecord
from finlaya.database.repository import DatabaseRepository
from .base import (
    ExecutionBroker,
    OrderSide,
    OrderStatus,
    PaperOrder,
    PaperPosition,
    PositionSide,
)
from .fills import calculate_fill_price

logger = get_logger("paper_broker")


class PaperBroker:
    """Simulated execution engine that fills orders against live market quotes."""

    def __init__(
        self,
        cache: MarketDataCache,
        ce_key: str,
        pe_key: str,
        price_fallback: str = "ltp",
        repository: DatabaseRepository | None = None,
    ):
        self.cache = cache
        self.ce_key = ce_key
        self.pe_key = pe_key
        self.price_fallback = price_fallback
        self.repository = repository

        self._order_counter: int = 0
        self._orders: dict[int, PaperOrder] = {}
        self._position: PaperPosition = PaperPosition()

    def get_position(self) -> PaperPosition:
        return self._position

    def get_order(self, order_id: int) -> PaperOrder | None:
        return self._orders.get(order_id)

    async def cancel_order(self, order_id: int) -> bool:
        order = self._orders.get(order_id)
        if order and order.status == OrderStatus.PENDING:
            order.status = OrderStatus.CANCELLED
            order.reason = "User or scheduler cancellation"
            if self.repository:
                await self.repository.update_order(order_id, status=OrderStatus.CANCELLED.value, reason=order.reason)
            return True
        return False

    async def submit_market_order(
        self,
        instrument_key: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        session_id: int,
    ) -> PaperOrder:
        """Execute a simulated market order against current cache quote."""
        self._order_counter += 1
        order_id = self._order_counter
        ts_str = now_ist().isoformat()

        quote = self.cache.get_quote(instrument_key)
        ltp = quote.ltp if quote else 0.0
        ask = quote.ask if quote else None
        bid = quote.bid if quote else None

        order = PaperOrder(
            order_id=order_id,
            session_id=session_id,
            timestamp=ts_str,
            instrument_key=instrument_key,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="MARKET",
            requested_price=ltp,
            status=OrderStatus.PENDING,
        )
        self._orders[order_id] = order

        if self.repository:
            await self.repository.save_order(
                OrderRecord(
                    id=order_id,
                    session_id=session_id,
                    timestamp=ts_str,
                    instrument=symbol,
                    side=side.value,
                    quantity=quantity,
                    order_type="MARKET",
                    requested_price=ltp,
                    status=OrderStatus.PENDING.value,
                )
            )

        # Execute simulated fill
        try:
            fill_price, source = calculate_fill_price(
                side=side,
                ask=ask,
                bid=bid,
                ltp=ltp,
                price_fallback=self.price_fallback,
            )
            order.fill_price = fill_price
            order.pricing_source = source
            order.status = OrderStatus.FILLED

            logger.info(
                f"Paper order #{order_id} FILLED: {side.value} {quantity}x {symbol} @ {fill_price:.2f} (source={source})",
                LogEvent.ORDER_FILLED,
                metadata={
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": side.value,
                    "quantity": quantity,
                    "fill_price": fill_price,
                    "source": source,
                },
            )

            # Update paper position state
            self._update_position_on_fill(instrument_key, symbol, side, quantity, fill_price)

            if self.repository:
                await self.repository.update_order(
                    order_id=order_id,
                    status=OrderStatus.FILLED.value,
                    fill_price=fill_price,
                )
                await self.repository.save_position(
                    PositionRecord(
                        session_id=session_id,
                        timestamp=now_ist().isoformat(),
                        instrument=self._position.symbol or "FLAT",
                        side=self._position.side.value,
                        quantity=self._position.quantity,
                        entry_price=self._position.entry_price,
                        exit_price=fill_price if side == OrderSide.SELL else None,
                        realized_pnl=self._position.realized_pnl,
                        unrealized_pnl=self._position.unrealized_pnl,
                    )
                )

        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.reason = str(e)
            logger.error(f"Paper order #{order_id} REJECTED: {e}", LogEvent.ERROR)
            if self.repository:
                await self.repository.update_order(
                    order_id=order_id,
                    status=OrderStatus.REJECTED.value,
                    reason=str(e),
                )

        return order

    def _update_position_on_fill(
        self,
        instrument_key: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        fill_price: float,
    ) -> None:
        if side == OrderSide.BUY:
            # Entering new long position
            new_side = PositionSide.LONG_CE if instrument_key == self.ce_key else PositionSide.LONG_PE
            self._position.instrument_key = instrument_key
            self._position.symbol = symbol
            self._position.side = new_side
            self._position.quantity = quantity
            self._position.entry_price = fill_price
            self._position.current_price = fill_price
            self._position.unrealized_pnl = 0.0
            logger.info(f"Opened paper position: {new_side.value} {quantity} @ {fill_price:.2f}", LogEvent.POSITION_OPENED)

        elif side == OrderSide.SELL:
            # Closing existing long position
            if self._position.quantity > 0:
                pnl = (fill_price - self._position.entry_price) * quantity
                self._position.realized_pnl += pnl
                logger.info(
                    f"Closed paper position {self._position.side.value}: P&L = {pnl:+.2f} (Total Realized: {self._position.realized_pnl:+.2f})",
                    LogEvent.ORDER_FILLED,
                )

            self._position.instrument_key = None
            self._position.symbol = None
            self._position.side = PositionSide.FLAT
            self._position.quantity = 0
            self._position.entry_price = 0.0
            self._position.current_price = 0.0
            self._position.unrealized_pnl = 0.0

    def refresh_unrealized_pnl(self) -> float:
        """Update unrealized P&L from latest cache price."""
        if self._position.side == PositionSide.FLAT or not self._position.instrument_key:
            self._position.unrealized_pnl = 0.0
            return 0.0

        quote = self.cache.get_quote(self._position.instrument_key)
        if quote and quote.ltp > 0:
            self._position.current_price = quote.ltp
            self._position.unrealized_pnl = round(
                (quote.ltp - self._position.entry_price) * self._position.quantity, 2
            )
        return self._position.unrealized_pnl
