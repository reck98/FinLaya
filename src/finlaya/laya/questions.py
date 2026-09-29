"""Deterministic question builders for Laya decision model."""

from __future__ import annotations

from typing import Any


def build_laya_question(position_side: str) -> dict[str, Any]:
    """Construct deterministic choice question for Laya based on position state."""
    instructions = (
        "Based only on the supplied market state, choose the most appropriate directional "
        "action for the NIFTY options strategy for the current decision horizon."
    )

    if position_side == "FLAT":
        return {
            "trading_action": {
                "type": "choice",
                "instructions": instructions,
                "criteria": {
                    "BUY": "Take/maintain a bullish directional position by holding the selected CE.",
                    "SELL": "Take/maintain a bearish directional position by holding the selected PE.",
                },
            }
        }
    else:
        return {
            "trading_action": {
                "type": "choice",
                "instructions": instructions,
                "criteria": {
                    "BUY": "The strategy should be LONG CE.",
                    "SELL": "The strategy should be LONG PE.",
                    "HOLD": "Do not change the existing position.",
                },
            }
        }
