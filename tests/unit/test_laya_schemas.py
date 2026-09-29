"""Unit tests for Laya decision schemas, questions, and response parsing."""

import pytest
from pydantic import ValidationError
from finlaya.laya.model import LayaDecisionModel
from finlaya.laya.questions import build_laya_question
from finlaya.laya.schemas import LayaDecision


def test_laya_decision_valid():
    d1 = LayaDecision(action="BUY", confidence=0.75)
    assert d1.action == "BUY"
    assert d1.confidence == 0.75

    d2 = LayaDecision(action="SELL", confidence=0.60)
    assert d2.action == "SELL"
    assert d2.confidence == 0.60

    d3 = LayaDecision(action="HOLD", confidence=1.0)
    assert d3.action == "HOLD"
    assert d3.confidence == 1.0

    d4 = LayaDecision(action="BUY", confidence=0.0)
    assert d4.confidence == 0.0


def test_laya_decision_invalid():
    # Confidence out of bounds
    with pytest.raises(ValidationError):
        LayaDecision(action="BUY", confidence=1.05)

    with pytest.raises(ValidationError):
        LayaDecision(action="BUY", confidence=-0.1)

    # Invalid action
    with pytest.raises(ValidationError):
        LayaDecision(action="EXIT", confidence=0.8)  # type: ignore


def test_question_builder_flat():
    q = build_laya_question("FLAT")
    criteria = q["trading_action"]["criteria"]
    # In FLAT, ONLY BUY and SELL are present. HOLD must NOT be present.
    assert "BUY" in criteria
    assert "SELL" in criteria
    assert "HOLD" not in criteria
    assert len(criteria) == 2


def test_question_builder_active_position():
    q_ce = build_laya_question("LONG_CE")
    crit_ce = q_ce["trading_action"]["criteria"]
    assert "BUY" in crit_ce
    assert "SELL" in crit_ce
    assert "HOLD" in crit_ce
    assert len(crit_ce) == 3

    q_pe = build_laya_question("LONG_PE")
    crit_pe = q_pe["trading_action"]["criteria"]
    assert len(crit_pe) == 3


def test_parse_response_formats():
    model = LayaDecisionModel()

    # Format 1: answers with choice and score
    raw1 = {"answers": {"trading_action": {"choice": "BUY", "score": 0.82}}}
    d1 = model._parse_response(raw1)
    assert d1 is not None
    assert d1.action == "BUY"
    assert d1.confidence == 0.82

    # Format 2: direct trading_action dictionary
    raw2 = {"trading_action": {"choice": "SELL", "confidence": 0.65}}
    d2 = model._parse_response(raw2)
    assert d2 is not None
    assert d2.action == "SELL"
    assert d2.confidence == 0.65

    # Format 3: malformed / missing
    assert model._parse_response({}) is None
    assert model._parse_response({"answers": {}}) is None
    assert model._parse_response({"answers": {"trading_action": {"choice": "UNKNOWN", "score": 0.9}}}) is None
    assert model._parse_response({"answers": {"trading_action": {"choice": "BUY", "score": "invalid"}}}) is None
    assert model._parse_response(None) is None
