"""Main FinLaya trading strategy execution loop and lifecycle manager."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from finlaya.config.settings import AppConfig
from finlaya.database.models import LayaDecisionRecord, MarketSnapshotRecord
from finlaya.database.repository import DatabaseRepository
from finlaya.execution.base import PositionSide
from finlaya.execution.order_manager import AtomicOrderManager
from finlaya.execution.paper_broker import PaperBroker
from finlaya.laya.base import DecisionModel
from finlaya.laya.questions import build_laya_question
from finlaya.laya.schemas import LayaDecision
from finlaya.market.candles import CandleEngine
from finlaya.market.feature_engine import FeatureEngine
from finlaya.market.state import MarketDataCache
from finlaya.risk.risk_engine import RiskEngine
from finlaya.scheduler.trading_clock import SessionPhase, TradingClock
from finlaya.strategy.state_machine import StrategyStateMachine, StrategyState, TransitionTrigger
from finlaya.utils.time import now_ist

logger = get_logger("strategy")


class FinLayaStrategy:
    """Core FinLaya quantitative strategy coordinator."""

    def __init__(
        self,
        session_id: int,
        config: AppConfig,
        cache: MarketDataCache,
        candle_engine: CandleEngine,
        feature_engine: FeatureEngine,
        model: DecisionModel,
        broker: PaperBroker,
        order_manager: AtomicOrderManager,
        risk_engine: RiskEngine,
        trading_clock: TradingClock,
        nifty_key: str,
        repository: DatabaseRepository | None = None,
        telemetry: Any | None = None,
    ):
        self.session_id = session_id
        self.config = config
        self.cache = cache
        self.candle_engine = candle_engine
        self.feature_engine = feature_engine
        self.model = model
        self.broker = broker
        self.order_manager = order_manager
        self.risk_engine = risk_engine
        self.trading_clock = trading_clock
        self.nifty_key = nifty_key
        self.repository = repository
        self.telemetry = telemetry

        self.fsm = StrategyStateMachine(confidence_threshold=config.strategy.confidence_threshold)
        self._running = False
        self._tracked_keys = [nifty_key, order_manager.ce_key, order_manager.pe_key]

    async def run_step(self) -> None:
        """Execute one 0.5-second decision cycle."""
        # 1. Update live candle engine from current spot tick
        nifty_quote = self.cache.get_quote(self.nifty_key)
        if nifty_quote and nifty_quote.ltp > 0:
            self.candle_engine.add_tick(nifty_quote.ist_time, nifty_quote.ltp, volume=nifty_quote.volume)

        # 2. Check market data freshness
        is_fresh = self.risk_engine.check_market_data_freshness(self.cache, self._tracked_keys)
        if not is_fresh:
            return

        # 3. Guard against overlapping transitions
        if self.order_manager.is_busy():
            return

        # 4. Freeze market state snapshot
        pos = self.broker.get_position()
        candles = self.candle_engine.get_completed_candles()
        seconds_to_exit = self.trading_clock.seconds_until_forced_exit()

        snapshot = self.feature_engine.build_snapshot(
            cache=self.cache,
            nifty_key=self.nifty_key,
            current_position_side=pos.side.value,
            current_quantity=pos.quantity,
            entry_price=pos.entry_price,
            seconds_to_exit=seconds_to_exit,
            candles=candles,
        )

        # 5. Persist market snapshot to database for quantitative research
        if self.repository:
            await self.repository.save_market_snapshot(
                MarketSnapshotRecord(
                    timestamp=snapshot.session.timestamp,
                    nifty_spot=snapshot.underlying.spot,
                    ce_ltp=snapshot.selected_contracts.ce.ltp,
                    pe_ltp=snapshot.selected_contracts.pe.ltp,
                    ce_bid=snapshot.selected_contracts.ce.bid,
                    ce_ask=snapshot.selected_contracts.ce.ask,
                    pe_bid=snapshot.selected_contracts.pe.bid,
                    pe_ask=snapshot.selected_contracts.pe.ask,
                    ce_volume=snapshot.selected_contracts.ce.volume,
                    pe_volume=snapshot.selected_contracts.pe.volume,
                    ce_oi=snapshot.selected_contracts.ce.oi,
                    pe_oi=snapshot.selected_contracts.pe.oi,
                )
            )

        if self.telemetry:
            self.telemetry.emit(
                "market_update",
                {
                    "nifty_spot": snapshot.underlying.spot,
                    "ce_ltp": snapshot.selected_contracts.ce.ltp,
                    "pe_ltp": snapshot.selected_contracts.pe.ltp,
                    "ce_bid": snapshot.selected_contracts.ce.bid,
                    "ce_ask": snapshot.selected_contracts.ce.ask,
                    "pe_bid": snapshot.selected_contracts.pe.bid,
                    "pe_ask": snapshot.selected_contracts.pe.ask,
                    "ce_volume": snapshot.selected_contracts.ce.volume,
                    "pe_volume": snapshot.selected_contracts.pe.volume,
                    "ce_oi": snapshot.selected_contracts.ce.oi,
                    "pe_oi": snapshot.selected_contracts.pe.oi,
                    "timestamp": snapshot.session.timestamp,
                },
            )

        # 6. Build deterministic typed question
        questions = build_laya_question(pos.side.value)

        # 7. Query Laya decision model
        decision, latency_ms = self.model.predict(state=snapshot.to_laya_json(), questions=questions)

        if decision is not None:
            logger.info(
                f"Laya Decision: {decision.action} (conf={decision.confidence:.4f}, latency={latency_ms:.1f}ms)",
                LogEvent.LAYA_INFERENCE,
                metadata={"action": decision.action, "confidence": decision.confidence, "latency_ms": latency_ms},
            )

        # 8. Evaluate decision through strategy FSM
        trigger, accepted, reason = self.fsm.evaluate_decision(decision)

        # Check if full verbose Laya inspection is enabled in config
        log_full = (
            getattr(self.config.laya, "log_full_inference", False)
            or getattr(self.config.logging, "log_laya_full", False)
        )
        if log_full:
            raw_res = getattr(self.model, "last_raw_response", None)
            self._render_verbose_inference(
                snapshot=snapshot,
                questions=questions,
                raw_response=raw_res,
                decision=decision,
                latency_ms=latency_ms,
                trigger=trigger,
                accepted=accepted,
                reason=reason,
            )

        # 9. Persist decision record to database
        if self.repository:
            await self.repository.save_laya_decision(
                LayaDecisionRecord(
                    session_id=self.session_id,
                    timestamp=now_ist().isoformat(),
                    position_before=pos.side.value,
                    question_options=json.dumps(questions),
                    action=decision.action if decision else "NONE",
                    confidence=decision.confidence if decision else 0.0,
                    accepted=1 if accepted else 0,
                    state_json=snapshot.to_laya_json(),
                    inference_latency_ms=latency_ms,
                )
            )

        if self.telemetry:
            self.telemetry.emit(
                "laya_decision",
                {
                    "session_id": self.session_id,
                    "action": decision.action if decision else "NONE",
                    "confidence": round(decision.confidence, 4) if decision else 0.0,
                    "position_before": pos.side.value,
                    "position_after": self.fsm.current_state.value,
                    "question_options": questions,
                    "inference_latency_ms": round(latency_ms, 1),
                    "accepted": bool(accepted),
                    "result": trigger.value if trigger else "HOLD POSITION",
                    "timestamp": now_ist().isoformat(),
                },
            )

        # 10. Execute atomic transitions if trigger fired
        if accepted:
            if trigger == TransitionTrigger.OPEN_LONG_CE:
                success = await self.order_manager.open_from_flat(PositionSide.LONG_CE, self.session_id)
                if success:
                    self.fsm.set_state(StrategyState.LONG_CE)

            elif trigger == TransitionTrigger.OPEN_LONG_PE:
                success = await self.order_manager.open_from_flat(PositionSide.LONG_PE, self.session_id)
                if success:
                    self.fsm.set_state(StrategyState.LONG_PE)

            elif trigger == TransitionTrigger.SWITCH_TO_PE:
                success = await self.order_manager.switch_ce_to_pe(self.session_id)
                if success:
                    self.fsm.set_state(StrategyState.LONG_PE)

            elif trigger == TransitionTrigger.SWITCH_TO_CE:
                success = await self.order_manager.switch_pe_to_ce(self.session_id)
                if success:
                    self.fsm.set_state(StrategyState.LONG_CE)

        # 11. Refresh unrealized P&L
        self.broker.refresh_unrealized_pnl()

    def _render_verbose_inference(
        self,
        snapshot: Any,
        questions: dict[str, Any],
        raw_response: Any,
        decision: Any,
        latency_ms: float,
        trigger: Any,
        accepted: bool,
        reason: str | None = None,
    ) -> None:
        """Render structured terminal output of state, question, and raw response safely on all consoles."""
        from rich import box
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        try:
            state_dict = json.loads(snapshot.to_laya_json()) if hasattr(snapshot, "to_laya_json") else snapshot
            state_str = json.dumps(state_dict, indent=2)
        except Exception:
            state_str = str(snapshot)

        question_str = json.dumps(questions, indent=2)
        raw_res_str = json.dumps(raw_response, indent=2) if raw_response is not None else "{}"

        verdict_color = "green" if accepted else "yellow"
        action_name = decision.action if decision else "NONE"
        conf_val = decision.confidence if decision else 0.0

        panel_content = (
            f"[bold cyan]--- 1. MARKET STATE SENT TO LAYA ---[/bold cyan]\n"
            f"[dim]{state_str}[/dim]\n\n"
            f"[bold magenta]--- 2. TYPED QUESTION & CRITERIA ---[/bold magenta]\n"
            f"{question_str}\n\n"
            f"[bold yellow]--- 3. RAW LAYA MODEL RESPONSE ---[/bold yellow]\n"
            f"[bold]{raw_res_str}[/bold]\n\n"
            f"[bold {verdict_color}]--- 4. DECISION EVALUATION ---[/bold {verdict_color}]\n"
            f"Action: [bold]{action_name}[/bold] | "
            f"Confidence: [bold]{conf_val:.4f}[/bold] (Threshold: {self.config.strategy.confidence_threshold:.2f}) | "
            f"Accepted: [{verdict_color}][bold]{accepted}[/bold][/{verdict_color}] | "
            f"Latency: [bold]{latency_ms:.1f}ms[/bold] | "
            f"Result: [bold]{trigger.value if trigger else 'HOLD'}[/bold]"
        )

        console.print(
            Panel(
                panel_content,
                title=f"[bold white on blue] LAYA FULL INFERENCE INSPECTION ({now_ist().strftime('%H:%M:%S IST')}) [/bold white on blue]",
                border_style="cyan",
                box=box.ASCII,
            )
        )

    async def execute_forced_exit(self) -> None:
        """Square off open positions and mark session completed at 15:13."""
        logger.info("Triggering forced exit procedure at 15:13 Asia/Kolkata...", LogEvent.FORCED_EXIT)
        # Cancel any pending orders and close all open positions
        await self.order_manager.close_all(self.session_id, reason="FORCED_EXIT_15_13")
        self.fsm.set_state(StrategyState.FLAT)

        pos = self.broker.get_position()
        logger.info(
            f"Trading session finalized: Final Position={pos.side.value}, Realized P&L = {pos.realized_pnl:+.2f}",
            LogEvent.SESSION_COMPLETED,
            metadata={"realized_pnl": pos.realized_pnl},
        )

        if self.repository:
            await self.repository.update_session_status(
                session_id=self.session_id,
                status="COMPLETED",
                ended_at=now_ist().isoformat(),
            )

        if self.telemetry:
            self.telemetry.record_heartbeat(session_id=self.session_id, status="COMPLETED")

    async def shutdown(self, reason: str = "GRACEFUL_SHUTDOWN") -> None:
        """Gracefully stop strategy, cancel orders, square off positions, and update session."""
        self._running = False
        logger.info(f"Graceful shutdown initiated ({reason})...", LogEvent.APPLICATION_START)

        # 1. Close all active orders and square off open positions
        try:
            await self.order_manager.close_all(self.session_id, reason=reason)
        except Exception as e:
            logger.warning(f"Error squaring off positions on shutdown: {e}")

        # 2. Reset FSM to FLAT
        self.fsm.set_state(StrategyState.FLAT)

        pos = self.broker.get_position()
        logger.info(
            f"Strategy shutdown complete: Position={pos.side.value}, Realized P&L = {pos.realized_pnl:+.2f}",
            LogEvent.SESSION_COMPLETED,
            metadata={"realized_pnl": pos.realized_pnl, "reason": reason},
        )

        # 3. Update database session status
        if self.repository:
            await self.repository.update_session_status(
                session_id=self.session_id,
                status="STOPPED",
                ended_at=now_ist().isoformat(),
            )

        # 4. Update telemetry heartbeat
        if self.telemetry:
            self.telemetry.record_heartbeat(session_id=self.session_id, status="STOPPED")

    async def run(self) -> None:
        """Run the strategy session until forced exit or stopped."""
        self._running = True

        # Pre-market wait if before 09:27
        if self.trading_clock.get_phase() == SessionPhase.WAITING_FOR_OPEN:
            await self.trading_clock.wait_until_start()

        self.trading_clock.scheduler.start()
        logger.info("Entering 0.5s decision loop...", LogEvent.APPLICATION_START)

        while self._running:
            phase = self.trading_clock.get_phase()
            if phase == SessionPhase.FORCED_EXIT:
                logger.info("Forced exit time reached (>= 15:13:00 IST).", LogEvent.FORCED_EXIT)
                await self.execute_forced_exit()
                break

            if self.telemetry:
                self.telemetry.record_heartbeat(session_id=self.session_id, status="RUNNING")

            await self.run_step()
            await self.trading_clock.scheduler.sleep_until_next_tick()

        self._running = False
