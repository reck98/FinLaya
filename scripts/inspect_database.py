"""Quantitative research inspection script for FinLaya SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()


def inspect_database(db_path: str = "data/finlaya.db") -> None:
    path = Path(db_path)
    if not path.exists():
        console.print(f"[bold red]Database file not found at {db_path}[/bold red]")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Trading Sessions Overview
    cursor.execute("SELECT * FROM trading_sessions ORDER BY id DESC")
    sessions = cursor.fetchall()

    console.print(f"\n[bold cyan]=== FinLaya Database: {db_path} ===[/bold cyan]")
    console.print(f"Total Trading Sessions: {len(sessions)}\n")

    if not sessions:
        console.print("[yellow]No sessions recorded yet.[/yellow]")
        conn.close()
        return

    sessions_table = Table(title="Trading Sessions")
    sessions_table.add_column("ID", justify="right")
    sessions_table.add_column("Date")
    sessions_table.add_column("Status")
    sessions_table.add_column("Spot Start", justify="right")
    sessions_table.add_column("Strike", justify="right")
    sessions_table.add_column("Expiry")
    sessions_table.add_column("Lot Size", justify="right")
    sessions_table.add_column("CE Key")
    sessions_table.add_column("PE Key")

    for s in sessions:
        sessions_table.add_row(
            str(s["id"]),
            str(s["trading_date"]),
            str(s["status"]),
            f"{s['nifty_spot_at_start'] or 0.0:.1f}",
            str(s["selected_strike"]),
            str(s["expiry"]),
            str(s["lot_size"]),
            str(s["ce_instrument_key"]),
            str(s["pe_instrument_key"]),
        )
    console.print(sessions_table)

    # 2. Detailed Quantitative Research Metrics for Latest Session
    latest = sessions[0]
    sess_id = latest["id"]

    console.print(f"\n[bold magenta]=== Quantitative Telemetry: Session #{sess_id} ({latest['trading_date']}) ===[/bold magenta]")

    # Decision signal breakdown
    cursor.execute(
        """
        SELECT
            COUNT(*) as total_decisions,
            SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) as buy_count,
            SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) as sell_count,
            SUM(CASE WHEN action = 'HOLD' THEN 1 ELSE 0 END) as hold_count,
            AVG(confidence) as avg_conf,
            AVG(inference_latency_ms) as avg_latency,
            MIN(inference_latency_ms) as min_latency,
            MAX(inference_latency_ms) as max_latency
        FROM laya_decisions
        WHERE session_id = ?
        """,
        (sess_id,),
    )
    dec_stats = cursor.fetchone()

    # Direction switches count
    cursor.execute(
        """
        SELECT action, position_before, accepted
        FROM laya_decisions
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (sess_id,),
    )
    all_decisions = cursor.fetchall()
    direction_switches = 0
    prev_act = None
    for d in all_decisions:
        act = d["action"]
        if prev_act and act in ("BUY", "SELL") and prev_act in ("BUY", "SELL") and act != prev_act:
            direction_switches += 1
        if act in ("BUY", "SELL"):
            prev_act = act

    # Orders & Slippage
    cursor.execute(
        """
        SELECT
            COUNT(*) as total_orders,
            SUM(CASE WHEN status = 'FILLED' THEN 1 ELSE 0 END) as filled_orders,
            AVG(ABS(fill_price - requested_price)) as avg_slippage,
            MAX(ABS(fill_price - requested_price)) as max_slippage
        FROM orders
        WHERE session_id = ? AND status = 'FILLED'
        """,
        (sess_id,),
    )
    order_stats = cursor.fetchone()

    # P&L
    cursor.execute(
        """
        SELECT realized_pnl, unrealized_pnl
        FROM positions
        WHERE session_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (sess_id,),
    )
    pnl_row = cursor.fetchone()
    realized_pnl = pnl_row["realized_pnl"] if pnl_row else 0.0

    metrics_table = Table(title=f"Session #{sess_id} Research Summary")
    metrics_table.add_column("Research Metric", style="cyan")
    metrics_table.add_column("Result", style="bold green")

    total_d = dec_stats["total_decisions"] or 0
    metrics_table.add_row("Total Decisions Generated", str(total_d))
    metrics_table.add_row("BUY Decisions", str(dec_stats["buy_count"] or 0))
    metrics_table.add_row("SELL Decisions", str(dec_stats["sell_count"] or 0))
    metrics_table.add_row("HOLD Decisions", str(dec_stats["hold_count"] or 0))
    metrics_table.add_row("Average Model Confidence", f"{(dec_stats['avg_conf'] or 0.0) * 100:.2f}%")
    metrics_table.add_row("Direction Switches (Reversals)", str(direction_switches))
    metrics_table.add_row("Avg Inference Latency", f"{dec_stats['avg_latency'] or 0.0:.2f} ms")
    metrics_table.add_row("Min / Max Latency", f"{dec_stats['min_latency'] or 0.0:.1f} ms / {dec_stats['max_latency'] or 0.0:.1f} ms")
    metrics_table.add_row("Total Orders Submitted", str(order_stats["total_orders"] or 0))
    metrics_table.add_row("Filled Orders", str(order_stats["filled_orders"] or 0))
    metrics_table.add_row("Average Simulated Slippage", f"{order_stats['avg_slippage'] or 0.0:.2f} pts")
    metrics_table.add_row("Max Simulated Slippage", f"{order_stats['max_slippage'] or 0.0:.2f} pts")
    metrics_table.add_row("Final Realized P&L", f"{realized_pnl:+.2f}")

    console.print(metrics_table)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect FinLaya SQLite database.")
    parser.add_argument("--db", default="data/finlaya.db", help="Path to finlaya.db")
    args = parser.parse_args()
    inspect_database(args.db)
