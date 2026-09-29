import math
import logging
from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger

logger = get_logger("strike_selector")


def select_nearest_strike(spot: float, step: int = 50) -> int:
    """Round the NIFTY spot price to the nearest integer multiple of `step` (default 50) using round half-up.
    
    Examples:
        23456.25 -> 23450
        23424.0 -> 23400
        23425.0 -> 23450
        23475.0 -> 23500
        23525.0 -> 23550
    """
    if step <= 0:
        raise ValueError(f"Step must be positive, got {step}")
    return int(math.floor(spot / step + 0.5) * step)


class StrikeSelector:
    """Manages the immutable strike selection for the entire trading session."""

    def __init__(self, step: int = 50):
        self.step = step
        self._selected_strike: int | None = None
        self._spot_at_selection: float | None = None

    @property
    def selected_strike(self) -> int | None:
        return self._selected_strike

    @property
    def spot_at_selection(self) -> float | None:
        return self._spot_at_selection

    def initialize_strike(self, spot: float) -> int:
        """Select and freeze the strike for the session.
        
        Immutable once initialized.
        """
        if self._selected_strike is not None:
            logger.warning(
                f"Attempted to re-select strike! Strike is immutable: {self._selected_strike}. Spot was {spot}"
            )
            return self._selected_strike

        self._spot_at_selection = spot
        self._selected_strike = select_nearest_strike(spot, self.step)

        logger.info(
            f"Selected immutable session strike: {self._selected_strike} from NIFTY spot={spot:.2f} (step={self.step})",
            LogEvent.STRIKE_SELECTED,
            metadata={"spot": spot, "strike": self._selected_strike, "step": self.step},
        )
        return self._selected_strike
