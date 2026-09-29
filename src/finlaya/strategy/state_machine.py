"""Finite State Machine for FinLaya options directional strategy."""

from __future__ import annotations

from enum import Enum
from typing import Any
from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from finlaya.laya.schemas import LayaDecision

logger = get_logger("state_machine")


class StrategyState(str, Enum):
    FLAT = "FLAT"
    LONG_CE = "LONG_CE"
    LONG_PE = "LONG_PE"


class TransitionTrigger(str, Enum):
    NO_ACTION = "NO_ACTION"
    OPEN_LONG_CE = "OPEN_LONG_CE"
    OPEN_LONG_PE = "OPEN_LONG_PE"
    SWITCH_TO_PE = "SWITCH_TO_PE"
    SWITCH_TO_CE = "SWITCH_TO_CE"
    FORCED_CLOSE = "FORCED_CLOSE"


class StrategyStateMachine:
    """Manages strategy position state and verifies allowed transitions."""

    def __init__(self, confidence_threshold: float = 0.60):
        self.confidence_threshold = confidence_threshold
        self._state: StrategyState = StrategyState.FLAT

    @property
    def current_state(self) -> StrategyState:
        return self._state

    def set_state(self, new_state: StrategyState) -> None:
        """Update the FSM state directly after execution verification."""
        self._state = new_state

    def evaluate_decision(self, decision: LayaDecision | None) -> tuple[TransitionTrigger, bool, str]:
        """Evaluate Laya decision against current FSM state.
        
        Returns:
            tuple[TransitionTrigger, bool, str]: (trigger, accepted, reason)
        """
        if decision is None:
            return TransitionTrigger.NO_ACTION, False, "Decision is None (malformed or timeout)"

        action = decision.action
        conf = decision.confidence

        # 1. Confidence threshold check: MUST be >= threshold
        if conf < self.confidence_threshold:
            reason = f"Confidence {conf:.4f} < threshold {self.confidence_threshold:.4f}"
            logger.info(f"Signal rejected: {action} with {reason}", LogEvent.SIGNAL_REJECTED)
            return TransitionTrigger.NO_ACTION, False, reason

        # 2. State-specific transition rules
        if self._state == StrategyState.FLAT:
            if action == "BUY":
                logger.info(f"Signal accepted: BUY (conf={conf:.4f}) -> OPEN_LONG_CE", LogEvent.SIGNAL_ACCEPTED)
                return TransitionTrigger.OPEN_LONG_CE, True, "Initial BUY from FLAT"
            elif action == "SELL":
                logger.info(f"Signal accepted: SELL (conf={conf:.4f}) -> OPEN_LONG_PE", LogEvent.SIGNAL_ACCEPTED)
                return TransitionTrigger.OPEN_LONG_PE, True, "Initial SELL from FLAT"
            elif action == "HOLD":
                # In FLAT state, HOLD is not a valid prompt option, but if received, no-op
                return TransitionTrigger.NO_ACTION, False, "HOLD received in FLAT state"

        elif self._state == StrategyState.LONG_CE:
            if action in ("BUY", "HOLD"):
                # Maintain existing CE position
                return TransitionTrigger.NO_ACTION, True, f"Continue holding LONG_CE on {action}"
            elif action == "SELL":
                logger.info(f"Signal accepted: SELL (conf={conf:.4f}) -> SWITCH_TO_PE", LogEvent.SIGNAL_ACCEPTED)
                return TransitionTrigger.SWITCH_TO_PE, True, "Switch LONG_CE to LONG_PE"

        elif self._state == StrategyState.LONG_PE:
            if action in ("SELL", "HOLD"):
                # Maintain existing PE position
                return TransitionTrigger.NO_ACTION, True, f"Continue holding LONG_PE on {action}"
            elif action == "BUY":
                logger.info(f"Signal accepted: BUY (conf={conf:.4f}) -> SWITCH_TO_CE", LogEvent.SIGNAL_ACCEPTED)
                return TransitionTrigger.SWITCH_TO_CE, True, "Switch LONG_PE to LONG_CE"

        return TransitionTrigger.NO_ACTION, False, f"Unhandled action {action} in state {self._state.value}"
