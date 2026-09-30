"""Local Laya decision model runner, parser, and mock implementations."""

from __future__ import annotations

import json
import time
from typing import Any

from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from .base import DecisionModel
from .schemas import LayaDecision

logger = get_logger("laya_model")


class LayaDecisionModel:
    """Local Laya decision inference engine using official open-source weights."""

    def __init__(self, model_id: str = "convaiinnovations/laya", device: str = "auto"):
        self.model_id = model_id
        self.device = device
        self._model: Any = None
        self._loaded: bool = False
        self.last_raw_response: dict[str, Any] | None = None

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """Load the Laya model locally into memory."""
        logger.info(f"Loading local Laya model from '{self.model_id}' (device={self.device})...", LogEvent.LAYA_LOADED)
        t0 = time.perf_counter()

        try:
            import laya

            # Try loading via laya.load or Router
            if hasattr(laya, "load"):
                self._model = laya.load(self.model_id)
            elif hasattr(laya, "Router"):
                self._model = laya.Router(preload=True)
            else:
                raise ImportError("Neither laya.load nor laya.Router found in laya package")

            self._loaded = True
            load_ms = (time.perf_counter() - t0) * 1000.0
            logger.info(f"Laya model successfully loaded in {load_ms:.1f}ms", LogEvent.LAYA_LOADED)
        except Exception as e:
            logger.error(f"Failed to load Laya model: {e}", LogEvent.ERROR)
            raise

    def health_check(self) -> bool:
        """Perform a test inference to verify model integrity and response latency."""
        if not self._loaded or self._model is None:
            return False

        logger.info("Running Laya startup health check inference...", LogEvent.LAYA_LOADED)
        test_state = {"test_metric": 100, "status": "warmup"}
        test_questions = {
            "trading_action": {
                "type": "choice",
                "instructions": "Select one option.",
                "criteria": {"BUY": "Bullish", "SELL": "Bearish"},
            }
        }
        decision, latency_ms = self.predict(test_state, test_questions)
        if decision is not None and latency_ms > 0:
            logger.info(
                f"Laya health check PASSED (latency={latency_ms:.1f}ms, sample_action={decision.action}, sample_conf={decision.confidence:.2f})",
                LogEvent.LAYA_LOADED,
            )
            return True
        logger.error("Laya health check FAILED: Model returned None or invalid output", LogEvent.ERROR)
        return False

    def predict(self, state: str | dict[str, Any], questions: dict[str, Any]) -> tuple[LayaDecision | None, float]:
        """Run decision inference over structured state and typed question.
        
        Returns:
            tuple[LayaDecision | None, float]: (decision if valid else None, latency_ms)
        """
        if not self._loaded or self._model is None:
            logger.error("Laya predict called before model was loaded", LogEvent.ERROR)
            return None, 0.0

        t0 = time.perf_counter()
        try:
            # If state is dict, convert to json string or pass directly
            if isinstance(state, dict):
                state_input = json.dumps(state)
            else:
                state_input = str(state)

            raw_res = self._model.predict(state_input, questions)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            self.last_raw_response = raw_res if isinstance(raw_res, dict) else {"raw": str(raw_res)}

            decision = self._parse_response(raw_res)
            return decision, latency_ms
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            self.last_raw_response = {"error": str(e)}
            logger.warning(f"Laya inference exception ({e}). Failing safe with DO NOTHING.", LogEvent.ERROR)
            return None, latency_ms

    def _parse_response(self, raw_res: Any) -> LayaDecision | None:
        """Parse raw Laya router/agent output into typed LayaDecision.
        
        If malformed or missing, returns None (DO NOTHING).
        """
        if not raw_res or not isinstance(raw_res, dict):
            return None

        # Check answers dictionary or top-level keys
        answers = raw_res.get("answers", raw_res)
        action_data = answers.get("trading_action")

        if not action_data:
            return None

        action_str = None
        confidence = None

        if isinstance(action_data, dict):
            action_str = action_data.get("choice") or action_data.get("action")

            # Prioritize choice softmax probability from 'probabilities' or 'answer_confidence'
            probs = action_data.get("probabilities")
            norm_probs = {str(k).strip().upper(): v for k, v in probs.items()} if isinstance(probs, dict) else {}
            if action_str and str(action_str).strip().upper() in norm_probs:
                confidence = norm_probs[str(action_str).strip().upper()]
            elif action_data.get("answer_confidence") is not None:
                confidence = action_data.get("answer_confidence")
            else:
                confidence = action_data.get("score") or action_data.get("confidence") or action_data.get("probability")
        elif isinstance(action_data, str):
            action_str = action_data
            confidence = raw_res.get("score", 1.0)

        if not action_str or confidence is None:
            return None

        action_str = str(action_str).strip().upper()
        if action_str not in ("BUY", "SELL", "HOLD"):
            logger.warning(f"Laya returned unexpected action: '{action_str}'")
            return None

        try:
            conf_float = float(confidence)
            if not (0.0 <= conf_float <= 1.0):
                logger.warning(f"Laya returned confidence outside [0, 1]: {conf_float}")
                return None

            return LayaDecision(action=action_str, confidence=conf_float)  # type: ignore
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not convert confidence '{confidence}' to float: {e}")
            return None


class MockDecisionModel:
    """Mock decision model for unit and integration testing without Hugging Face downloads."""

    def __init__(self, default_action: str = "BUY", default_confidence: float = 0.75, latency_ms: float = 15.0):
        self.default_action = default_action
        self.default_confidence = default_confidence
        self.latency_ms = latency_ms
        self._loaded: bool = False
        self._scripted_responses: list[tuple[str, float]] = []
        self.last_raw_response: dict[str, Any] | None = None

    def set_scripted_responses(self, responses: list[tuple[str, float]]) -> None:
        """Set an explicit sequence of (action, confidence) tuples for test execution."""
        self._scripted_responses = list(responses)

    def load(self) -> None:
        self._loaded = True

    def health_check(self) -> bool:
        return True

    def predict(self, state: str | dict[str, Any], questions: dict[str, Any]) -> tuple[LayaDecision | None, float]:
        if not self._loaded:
            return None, 0.0

        if self._scripted_responses:
            action, conf = self._scripted_responses.pop(0)
            self.last_raw_response = {
                "answers": {
                    "trading_action": {
                        "type": "choice",
                        "choice": action,
                        "confidence": conf,
                        "probabilities": {action: conf, "OTHER": round(max(0.0, 1.0 - conf), 4)},
                    }
                },
                "usage": {"input_tokens": 30, "output_tokens": 0},
            }
            return LayaDecision(action=action, confidence=conf), self.latency_ms  # type: ignore

        self.last_raw_response = {
            "answers": {
                "trading_action": {
                    "type": "choice",
                    "choice": self.default_action,
                    "confidence": self.default_confidence,
                    "probabilities": {self.default_action: self.default_confidence, "OTHER": round(max(0.0, 1.0 - self.default_confidence), 4)},
                }
            },
            "usage": {"input_tokens": 30, "output_tokens": 0},
        }
        return LayaDecision(action=self.default_action, confidence=self.default_confidence), self.latency_ms  # type: ignore

