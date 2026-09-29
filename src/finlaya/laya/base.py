"""Protocol definition for decision models."""

from __future__ import annotations

from typing import Any, Protocol
from .schemas import LayaDecision


class DecisionModel(Protocol):
    """Protocol for local Laya model or mocks."""

    def load(self) -> None: ...
    def health_check(self) -> bool: ...
    def predict(self, state: str | dict[str, Any], questions: dict[str, Any]) -> tuple[LayaDecision | None, float]:
        """Run decision inference. Returns (decision, latency_ms)."""
        ...
