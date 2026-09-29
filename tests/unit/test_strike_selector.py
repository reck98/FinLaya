"""Unit tests for strike selector and rounding logic."""

import pytest
from finlaya.strategy.strike_selector import select_nearest_strike, StrikeSelector


def test_strike_rounding_nearest_50():
    assert select_nearest_strike(23456.25, 50) == 23450
    assert select_nearest_strike(23424.0, 50) == 23400
    assert select_nearest_strike(23474.9, 50) == 23450
    assert select_nearest_strike(23475.0, 50) == 23500
    assert select_nearest_strike(23500.0, 50) == 23500
    assert select_nearest_strike(23524.9, 50) == 23500
    assert select_nearest_strike(23525.0, 50) == 23550


def test_strike_rounding_invalid_step():
    with pytest.raises(ValueError):
        select_nearest_strike(23450, 0)
    with pytest.raises(ValueError):
        select_nearest_strike(23450, -50)


def test_strike_selector_immutability():
    selector = StrikeSelector(step=50)
    assert selector.selected_strike is None

    # First selection at 09:27
    strike = selector.initialize_strike(spot=23456.2)
    assert strike == 23450
    assert selector.selected_strike == 23450
    assert selector.spot_at_selection == 23456.2

    # Later price moves substantially to 23600
    strike_again = selector.initialize_strike(spot=23600.0)
    # MUST REMAIN 23450 (immutable for the session)
    assert strike_again == 23450
    assert selector.selected_strike == 23450
