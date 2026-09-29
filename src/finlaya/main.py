"""FinLaya main command-line interface and system orchestrator."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table

from finlaya.config.settings import AppConfig, load_config
from finlaya.database.database import DatabaseEngine
from finlaya.database.models import TradingSessionRecord
from finlaya.database.repository import SqliteRepository
from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger, setup_logging
from finlaya.laya.model import LayaDecisionModel, MockDecisionModel
from finlaya.broker.upstox_client import UpstoxClient
from finlaya.broker.upstox_instruments import UpstoxInstrumentService, NIFTY_UNDERLYING_KEY
from finlaya.broker.upstox_market_data import UpstoxMarketDataFeed
from finlaya.market.state import MarketDataCache
from finlaya.market.candles import CandleEngine
from finlaya.market.feature_engine import FeatureEngine
from finlaya.execution.paper_broker import PaperBroker
from finlaya.execution.order_manager import AtomicOrderManager
from finlaya.risk.risk_engine import RiskEngine
from finlaya.scheduler.trading_clock import TradingClock
from finlaya.strategy.strike_selector import StrikeSelector
from finlaya.strategy.strategy import FinLayaStrategy
from finlaya.utils.time import now_ist

app = typer.Typer(help="FinLaya — Local Laya NIFTY Options Paper-Trading System")
console = Console()
logger = get_logger("finlaya_main")


def print_banner(config: AppConfig) -> None:
    """Print the official FinLaya startup banner."""
    banner = f"""
[bold cyan]FinLaya[/bold cyan]
--------------------------------
[bold]Mode:[/bold] PAPER
[bold]Model:[/bold] {config.laya.model}
[bold]Broker Data:[/bold] Upstox (v3 WebSocket)
[bold]Timezone:[/bold] {config.project.timezone}
[bold]Decision Interval:[/bold] {config.strategy.decision_interval_seconds}s
[bold]Start:[/bold] {config.trading.start_time}
[bold]Force Exit:[/bold] {config.trading.force_exit_time}
[bold]Historical Candles:[/bold] {config.market_data.historical_candles}
[bold]Confidence Threshold:[/bold] {int(config.strategy.confidence_threshold * 100)}%
[bold]Lots:[/bold] {config.trading.lots}
[bold]Expected Lot Size:[/bold] {config.trading.expected_lot_size}
--------------------------------
"""
    console.print(banner)


@app.command()
def validate(config_path: str = "config/config.yaml") -> None:
    """Validate configuration, environment variables, and directories."""
    try:
        config = load_config(config_path)
        console.print("[green][OK] Configuration file valid.[/green]")

        # Check directories
        Path(config.logging.directory).mkdir(parents=True, exist_ok=True)
        Path(config.database.path).parent.mkdir(parents=True, exist_ok=True)
        console.print("[green][OK] Data and log directories accessible.[/green]")

        # Check access token
        if not config.upstox.access_token:
            console.print("[yellow][!] UPSTOX_ACCESS_TOKEN is not configured in .env (required for live broker connection).[/yellow]")
        else:
            console.print("[green][OK] Upstox access token detected.[/green]")

        print_banner(config)
    except Exception as e:
        console.print(f"[bold red]Validation failed: {e}[/bold red]")
        sys.exit(1)


@app.command()
def download_model(model_name: str = "convaiinnovations/laya", device: str = "auto") -> None:
    """Download/cache the Laya model locally and perform a health check inference."""
    console.print(f"[cyan]Downloading/verifying Laya model weights: {model_name}...[/cyan]")
    model = LayaDecisionModel(model_id=model_name, device=device)
    try:
        model.load()
        console.print("[green][OK] Laya model loaded successfully into memory.[/green]")
        healthy = model.health_check()
        if healthy:
            console.print("[bold green][OK] Laya startup health check PASSED![/bold green]")
        else:
            console.print("[bold red][X] Laya health check failed.[/bold red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Model download / verification failed: {e}[/bold red]")
        sys.exit(1)


@app.command()
def check_upstox(config_path: str = "config/config.yaml") -> None:
    """Validate Upstox API connectivity, NIFTY spot quote, and option chain discovery."""
    config = load_config(config_path)
    if not config.upstox.access_token:
        console.print("[bold red]UPSTOX_ACCESS_TOKEN is missing in .env[/bold red]")
        sys.exit(1)

    client = UpstoxClient(access_token=config.upstox.access_token)
    try:
        client.validate_connectivity()
        console.print("[green][OK] Upstox API connectivity verified.[/green]")

        is_open = client.check_market_open("NSE")
        console.print(f"Exchange NSE status: {'[green]OPEN / SCHEDULED[/green]' if is_open else '[yellow]CLOSED[/yellow]'}")

        svc = UpstoxInstrumentService(client.api_client)
        contracts = svc.fetch_all_nifty_contracts()
        expiries = svc.get_expiry_dates(contracts)
        console.print(f"[green][OK] Retrieved {len(contracts)} contracts across {len(expiries)} expiry dates.[/green]")

        # Check today expiry
        svc.verify_not_expiry_day(expiries)
        target_expiry = svc.select_target_expiry(expiries)
        console.print(f"Selected target expiry: [bold cyan]{target_expiry}[/bold cyan]")

        spot = svc.get_spot_price()
        selector = StrikeSelector(config.trading.strike_step)
        strike = selector.initialize_strike(spot)
        console.print(f"Current NIFTY Spot: [bold]{spot:.2f}[/bold] -> Selected Strike: [bold cyan]{strike}[/bold cyan]")

        ce_meta, pe_meta = svc.discover_contracts(
            contracts,
            strike,
            target_expiry,
            expected_lot_size=config.trading.expected_lot_size,
            enforce_lot_size=config.trading.enforce_expected_lot_size,
        )
        console.print(f"CE Contract: [green]{ce_meta.trading_symbol}[/green] ({ce_meta.instrument_key}) Lot: {ce_meta.lot_size}")
        console.print(f"PE Contract: [green]{pe_meta.trading_symbol}[/green] ({pe_meta.instrument_key}) Lot: {pe_meta.lot_size}")

    except Exception as e:
        console.print(f"[bold red]Upstox check failed: {e}[/bold red]")
        sys.exit(1)


@app.command()
def inspect_db(db_path: str = "data/finlaya.db") -> None:
    """Inspect recent session telemetry and performance in the SQLite database."""
    async def _inspect():
        repo = SqliteRepository(db_path)
        session = await repo.get_latest_session()
        if not session or not session.id:
            console.print("[yellow]No trading sessions found in database.[/yellow]")
            return

        stats = await repo.get_session_stats(session.id)
        table = Table(title=f"FinLaya Session #{session.id} Telemetry ({session.trading_date})")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold green")

        table.add_row("Status", str(session.status))
        table.add_row("Started At", str(session.started_at))
        table.add_row("Ended At", str(session.ended_at or "ACTIVE"))
        table.add_row("NIFTY Spot at Start", f"{session.nifty_spot_at_start or 0.0:.2f}")
        table.add_row("Selected Strike", str(session.selected_strike))
        table.add_row("Expiry", str(session.expiry))
        table.add_row("Lot Size", str(session.lot_size))
        table.add_row("Total Decisions", str(stats["total_decisions"]))
        table.add_row("BUY Signals", str(stats["buy_signals"]))
        table.add_row("SELL Signals", str(stats["sell_signals"]))
        table.add_row("HOLD Signals", str(stats["hold_signals"]))
        table.add_row("Accepted Signals", str(stats["accepted_signals"]))
        table.add_row("Avg Confidence", f"{stats['avg_confidence'] * 100:.1f}%")
        table.add_row("Avg Latency", f"{stats['avg_latency_ms']:.1f}ms")
        table.add_row("Orders Filled", f"{stats['filled_orders']}/{stats['total_orders']}")
        table.add_row("Realized P&L", f"{stats['realized_pnl']:+.2f}")

        console.print(table)

    asyncio.run(_inspect())


@app.command()
def status(db_path: str = "data/finlaya.db") -> None:
    """Quick status check of the last session."""
    inspect_db(db_path)


@app.command()
def run(config_path: str = "config/config.yaml", use_mock_laya: bool = False) -> None:
    """Start the FinLaya paper-trading session."""
    async def _run():
        config = load_config(config_path)
        setup_logging(log_level=config.logging.level, log_dir=config.logging.directory)
        logger.info("FinLaya paper-trading system starting...", LogEvent.APPLICATION_START)
        print_banner(config)

        # 1. Initialize SQLite Database
        db_engine = DatabaseEngine(config.database.path)
        await db_engine.initialize()
        repo = SqliteRepository(config.database.path)

        # 2. Initialize Upstox client
        if not config.upstox.access_token:
            logger.error("UPSTOX_ACCESS_TOKEN is missing. Please provide it in .env", LogEvent.ERROR)
            console.print("[bold red]UPSTOX_ACCESS_TOKEN is missing in .env[/bold red]")
            sys.exit(1)

        upstox = UpstoxClient(access_token=config.upstox.access_token)
        upstox.validate_connectivity()

        # 3. Market availability check
        if not upstox.check_market_open("NSE"):
            logger.error("Market is closed today. Terminating session.", LogEvent.MARKET_OPEN_CHECK)
            console.print("[bold red]Market is closed today. Strategy aborted.[/bold red]")
            sys.exit(0)

        # 4. Instrument and Expiry Discovery
        inst_service = UpstoxInstrumentService(upstox.api_client)
        contracts = inst_service.fetch_all_nifty_contracts()
        expiries = inst_service.get_expiry_dates(contracts)

        # Expiry Day Rule: FAIL CLOSED if today is expiry
        inst_service.verify_not_expiry_day(expiries)
        target_expiry = inst_service.select_target_expiry(expiries)

        # 5. Strike selection
        spot = inst_service.get_spot_price()
        strike_selector = StrikeSelector(step=config.trading.strike_step)
        selected_strike = strike_selector.initialize_strike(spot)

        # 6. Locate CE and PE contracts
        ce_meta, pe_meta = inst_service.discover_contracts(
            contracts=contracts,
            strike=selected_strike,
            target_expiry=target_expiry,
            expected_lot_size=config.trading.expected_lot_size,
            enforce_lot_size=config.trading.enforce_expected_lot_size,
        )

        # 7. Create Session in SQLite
        now_dt = now_ist()
        session_id = await repo.create_session(
            TradingSessionRecord(
                trading_date=now_dt.strftime("%Y-%m-%d"),
                started_at=now_dt.isoformat(),
                status="ACTIVE",
                nifty_spot_at_start=spot,
                selected_strike=selected_strike,
                expiry=target_expiry,
                ce_instrument_key=ce_meta.instrument_key,
                pe_instrument_key=pe_meta.instrument_key,
                lot_size=ce_meta.lot_size,
            )
        )
        logger.set_session_id(session_id)
        console.print(f"[bold green]Trading session #{session_id} initialized in database.[/bold green]")

        # 8. Load / Warm Laya Decision Model
        if use_mock_laya:
            logger.info("Using MockDecisionModel for simulation", LogEvent.LAYA_LOADED)
            model = MockDecisionModel()
            model.load()
        else:
            model = LayaDecisionModel(model_id=config.laya.model, device=config.laya.device)
            model.load()
            if not model.health_check():
                logger.error("Laya health check failed. Aborting session.", LogEvent.ERROR)
                await repo.update_session_status(session_id, status="ABORTED")
                sys.exit(1)

        # 9. Market Data & Execution Setup
        cache = MarketDataCache()
        candle_engine = CandleEngine(max_candles=config.market_data.historical_candles)
        feature_engine = FeatureEngine(
            strike=selected_strike,
            expiry=target_expiry,
            ce_key=ce_meta.instrument_key,
            ce_symbol=ce_meta.trading_symbol,
            pe_key=pe_meta.instrument_key,
            pe_symbol=pe_meta.trading_symbol,
        )

        broker = PaperBroker(
            cache=cache,
            ce_key=ce_meta.instrument_key,
            pe_key=pe_meta.instrument_key,
            price_fallback=config.paper_trading.price_fallback,
            repository=repo,
        )

        order_manager = AtomicOrderManager(
            broker=broker,
            ce_key=ce_meta.instrument_key,
            ce_symbol=ce_meta.trading_symbol,
            pe_key=pe_meta.instrument_key,
            pe_symbol=pe_meta.trading_symbol,
            lot_size=ce_meta.lot_size,
            num_lots=config.trading.lots,
        )

        risk_engine = RiskEngine(
            max_lots=config.trading.lots,
            lot_size=ce_meta.lot_size,
            max_staleness_seconds=config.market_data.max_staleness_seconds,
        )

        trading_clock = TradingClock(
            start_time_str=config.trading.start_time,
            force_exit_time_str=config.trading.force_exit_time,
            decision_interval_seconds=config.strategy.decision_interval_seconds,
        )

        # 10. Connect Market Data WebSocket
        ws_feed = UpstoxMarketDataFeed(api_client=upstox.api_client, cache=cache)
        ws_feed.subscribe([NIFTY_UNDERLYING_KEY, ce_meta.instrument_key, pe_meta.instrument_key])
        await ws_feed.connect()

        # 11. Run Strategy
        strategy = FinLayaStrategy(
            session_id=session_id,
            config=config,
            cache=cache,
            candle_engine=candle_engine,
            feature_engine=feature_engine,
            model=model,
            broker=broker,
            order_manager=order_manager,
            risk_engine=risk_engine,
            trading_clock=trading_clock,
            nifty_key=NIFTY_UNDERLYING_KEY,
            repository=repo,
        )

        try:
            await strategy.run()
        finally:
            await ws_feed.disconnect()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
