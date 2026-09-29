"""Unit tests for the strategy Finite State Machine and transition logic."""

import pytest
from finlaya.laya.schemas import LayaDecision
from finlaya.strategy.state_machine import StrategyStateMachine, StrategyState, TransitionTrigger


def test_fsm_initial_state_is_flat():
    fsm = StrategyStateMachine(confidence_threshold=0.60)
    assert fsm.current_state == StrategyState.FLAT


def test_fsm_flat_to_long_ce():
    fsm = StrategyStateMachine(confidence_threshold=0.60)
    # BUY >= 0.60
    trigger, accepted, reason = fsm.evaluate_decision(LayaDecision(action="BUY", confidence=0.60))
    assert trigger == TransitionTrigger.OPEN_LONG_CE
    assert accepted is True

    fsm.set_state(StrategyState.LONG_CE)
    assert fsm.current_state == StrategyState.LONG_CE


def test_fsm_flat_to_long_pe():
    fsm = StrategyStateMachine(confidence_threshold=0.60)
    # SELL >= 0.60
    trigger, accepted, reason = fsm.evaluate_decision(LayaDecision(action="SELL", confidence=0.75))
    assert trigger == TransitionTrigger.OPEN_LONG_PE
    assert accepted is True

    fsm.set_state(StrategyState.LONG_PE)
    assert fsm.current_state == StrategyState.LONG_PE


def test_fsm_confidence_threshold_exact_boundary():
    fsm = StrategyStateMachine(confidence_threshold=0.60)

    # 0.60 MUST qualify (confidence >= threshold)
    trigger, accepted, _ = fsm.evaluate_decision(LayaDecision(action="BUY", confidence=0.60))
    assert accepted is True
    assert trigger == TransitionTrigger.OPEN_LONG_CE

    # 0.599 MUST be rejected
    trigger_low, accepted_low, reason = fsm.evaluate_decision(LayaDecision(action="BUY", confidence=0.599))
    assert accepted_low is False
    assert trigger_low == TransitionTrigger.NO_ACTION
    assert "< threshold" in reason


def test_fsm_long_ce_transitions():
    fsm = StrategyStateMachine(confidence_threshold=0.60)
    fsm.set_state(StrategyState.LONG_CE)

    # BUY while LONG_CE -> maintain (no new order)
    tr_buy, acc_buy, _ = fsm.evaluate_decision(LayaDecision(action="BUY", confidence=0.85))
    assert tr_buy == TransitionTrigger.NO_ACTION
    assert acc_buy is True

    # HOLD while LONG_CE -> maintain
    tr_hold, acc_hold, _ = fsm.evaluate_decision(LayaDecision(action="HOLD", confidence=0.70))
    assert tr_hold == TransitionTrigger.NO_ACTION
    assert acc_hold is True

    # SELL while LONG_CE -> switch to PE
    tr_sell, acc_sell, _ = fsm.evaluate_decision(LayaDecision(action="SELL", confidence=0.65))
    assert tr_sell == TransitionTrigger.SWITCH_TO_PE
    assert acc_sell is True


def test_fsm_long_pe_transitions():
    fsm = StrategyStateMachine(confidence_threshold=0.60)
    fsm.set_state(StrategyState.LONG_PE)

    # SELL while LONG_PE -> maintain
    tr_sell, acc_sell, _ = fsm.evaluate_decision(LayaDecision(action="SELL", confidence=0.80))
    assert tr_sell == TransitionTrigger.NO_ACTION
    assert acc_sell is True

    # HOLD while LONG_PE -> maintain
    tr_hold, acc_hold, _ = fsm.evaluate_decision(LayaDecision(action="HOLD", confidence=0.60))
    assert tr_hold == TransitionTrigger.NO_ACTION
    assert acc_hold is True

    # BUY while LONG_PE -> switch to CE
    tr_buy, acc_buy, _ = fsm.evaluate_decision(LayaDecision(action="BUY", confidence=0.72))
    assert tr_buy == TransitionTrigger.SWITCH_TO_CE
    assert acc_buy is True


def test_fsm_handles_none_decision():
    fsm = StrategyStateMachine(confidence_threshold=0.60)
    trigger, accepted, reason = fsm.evaluate_decision(None)
    assert trigger == TransitionTrigger.NO_ACTION
    assert accepted is False
    assert "None" in reason
