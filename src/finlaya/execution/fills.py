"""Simulated fill pricing engine matching bids and asks with fallback to LTP."""

from __future__ import annotations

from .base import OrderSide


def calculate_fill_price(
    side: OrderSide | str,
    ask: float | None,
    bid: float | None,
    ltp: float,
    price_fallback: str = "ltp",
) -> tuple[float, str]:
    """Calculate simulated fill price and document pricing source.
    
    Returns:
        tuple[float, str]: (fill_price, pricing_source)
    """
    side_str = side.value if isinstance(side, OrderSide) else str(side).upper()

    if side_str == "BUY":
        if ask is not None and ask > 0:
            return float(ask), "ask"
        if price_fallback == "ltp" and ltp > 0:
            return float(ltp), "ltp_fallback"
        raise ValueError(f"Cannot fill BUY: Ask is unavailable ({ask}) and LTP fallback failed ({ltp})")

    elif side_str == "SELL":
        if bid is not None and bid > 0:
            return float(bid), "bid"
        if price_fallback == "ltp" and ltp > 0:
            return float(ltp), "ltp_fallback"
        raise ValueError(f"Cannot fill SELL: Bid is unavailable ({bid}) and LTP fallback failed ({ltp})")

    raise ValueError(f"Unsupported order side: {side_str}")
