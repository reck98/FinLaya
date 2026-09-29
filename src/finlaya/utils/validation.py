"""Validation utilities for quantitative parameters and inputs."""

from __future__ import annotations


def validate_strike_step(step: int) -> None:
    """Validate that strike step is a positive integer divisible by 10 or 50."""
    if step <= 0:
        raise ValueError(f"Strike step must be positive, got {step}")


def validate_lot_size(
    broker_lot_size: int,
    expected_lot_size: int | None,
    enforce: bool = True,
) -> tuple[bool, str]:
    """Validate broker-reported lot size against expected lot size.
    
    Returns (is_valid, message).
    """
    if broker_lot_size <= 0:
        return False, f"Invalid broker lot size: {broker_lot_size} <= 0"

    if expected_lot_size is None or not enforce:
        return True, f"Broker lot size {broker_lot_size} accepted (enforcement disabled)"

    if broker_lot_size != expected_lot_size:
        return (
            False,
            f"Lot size mismatch: Broker reports {broker_lot_size}, but expected {expected_lot_size}. "
            "Exchange or broker contract specs may have changed. Aborting for safety.",
        )

    return True, f"Lot size verified: Broker {broker_lot_size} matches expected {expected_lot_size}"


def validate_confidence(confidence: float) -> bool:
    """Validate that confidence is between 0.0 and 1.0 inclusive."""
    return 0.0 <= confidence <= 1.0
