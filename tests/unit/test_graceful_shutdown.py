"""Unit tests for graceful shutdown, colored console formatting, and verbose Laya inspection."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from finlaya.config.settings import AppConfig
from finlaya.logging.logger import ColoredConsoleFormatter, LogEvent
from finlaya.laya.model import MockDecisionModel, LayaDecision
from finlaya.execution.base import PositionSide
from finlaya.strategy.state_machine import StrategyState
from finlaya.strategy.strategy import FinLayaStrategy


def test_colored_console_formatter_styling_and_bifurcation():
    """Verify ColoredConsoleFormatter adds ANSI colors, redacts secrets, and adds newline for LAYA_INFERENCE."""
    formatter = ColoredConsoleFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    # 1. Normal record with secret
    record = logging.LogRecord(
        name="strategy",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Connected with Bearer secret_token_12345",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "[REDACTED]" in formatted
    assert "secret_token_12345" not in formatted
    assert "[INFO]" in formatted
    assert "[strategy]" in formatted

    # 2. LAYA_INFERENCE event should have leading newline
    rec_inference = logging.LogRecord(
        name="strategy",
        level=logging.INFO,
        pathname=__file__,
        lineno=20,
        msg="[LAYA_INFERENCE] Laya Decision: BUY",
        args=(),
        exc_info=None,
    )
    setattr(rec_inference, "event", LogEvent.LAYA_INFERENCE)
    formatted_inf = formatter.format(rec_inference)
    assert formatted_inf.startswith("\n")
    assert "[LAYA_INFERENCE]" in formatted_inf


@pytest.mark.asyncio
async def test_strategy_shutdown_lifecycle():
    """Verify strategy.shutdown squares off positions, resets FSM to FLAT, and marks session STOPPED."""
    mock_config = AppConfig()
    mock_cache = MagicMock()
    mock_candle_engine = MagicMock()
    mock_feature_engine = MagicMock()
    mock_model = MockDecisionModel()
    mock_broker = MagicMock()
    mock_broker.get_position.return_value = MagicMock(side=PositionSide.FLAT, realized_pnl=120.0)
    mock_order_manager = MagicMock()
    mock_order_manager.close_all = AsyncMock(return_value=True)
    mock_risk = MagicMock()
    mock_clock = MagicMock()
    mock_repo = MagicMock()
    mock_repo.update_session_status = AsyncMock()
    mock_telemetry = MagicMock()

    strategy = FinLayaStrategy(
        session_id=101,
        config=mock_config,
        cache=mock_cache,
        candle_engine=mock_candle_engine,
        feature_engine=mock_feature_engine,
        model=mock_model,
        broker=mock_broker,
        order_manager=mock_order_manager,
        risk_engine=mock_risk,
        trading_clock=mock_clock,
        nifty_key="NSE_INDEX|Nifty 50",
        repository=mock_repo,
        telemetry=mock_telemetry,
    )

    strategy._running = True
    strategy.fsm.set_state(StrategyState.LONG_CE)

    await strategy.shutdown(reason="USER_INTERRUPT")

    # Assert running flag is cleared
    assert not strategy._running
    # Assert FSM is set back to FLAT
    assert strategy.fsm.current_state == StrategyState.FLAT
    # Assert close_all was called
    mock_order_manager.close_all.assert_called_once_with(101, reason="USER_INTERRUPT")
    # Assert repository recorded STOPPED status
    mock_repo.update_session_status.assert_called_once()
    assert mock_repo.update_session_status.call_args[1]["status"] == "STOPPED"
    # Assert telemetry recorded STOPPED status
    mock_telemetry.record_heartbeat.assert_called_once_with(session_id=101, status="STOPPED")


def test_mock_decision_model_populates_last_raw_response():
    """Verify MockDecisionModel stores structured last_raw_response."""
    model = MockDecisionModel(default_action="BUY", default_confidence=0.85)
    model.load()

    decision, latency = model.predict(state={"spot": 22700}, questions={"trading_action": {}})
    assert decision is not None
    assert decision.action == "BUY"
    assert model.last_raw_response is not None
    assert "answers" in model.last_raw_response
    assert model.last_raw_response["answers"]["trading_action"]["choice"] == "BUY"
    assert model.last_raw_response["answers"]["trading_action"]["confidence"] == 0.85
