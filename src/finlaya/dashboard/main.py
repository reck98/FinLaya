"""Command-line interface for the FinLaya Real-Time Dashboard."""

from __future__ import annotations

import sys
from pathlib import Path
import typer
from rich.console import Console
import uvicorn

from .app import create_app

app = typer.Typer(help="FinLaya Real-Time Paper-Trading Dashboard")
console = Console()


@app.command()
def start(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host network interface to bind"),
    port: int = typer.Option(8765, "--port", "-p", help="Port to listen on"),
    db_path: str = typer.Option("data/finlaya.db", "--db-path", help="Path to SQLite paper-trading database"),
    mock: bool = typer.Option(False, "--mock", help="Run with synthetic real-time event generator (MOCK DATA)"),
    production: bool = typer.Option(False, "--production", help="Serve pre-built React frontend bundle"),
) -> None:
    """Launch the FinLaya Real-Time Trading Dashboard server."""
    mode_str = "[bold yellow]MOCK DATA[/bold yellow]" if mock else "[bold green]LIVE OBSERVABILITY (PAPER)[/bold green]"

    banner = f"""
[bold cyan]FinLaya Real-Time Trading Dashboard[/bold cyan]
------------------------------------------------
Mode:         {mode_str}
Address:      http://{host}:{port}
WebSocket:    ws://{host}:{port}/ws
Database:     {db_path}
Read-Only:    YES (No trading controls)
------------------------------------------------
"""
    console.print(banner)

    # Check for frontend build
    frontend_dist = Path("frontend/dist")
    if not mock and not frontend_dist.exists() and not (Path(__file__).parent / "static").exists():
        console.print("[yellow][!] Note: Frontend build not found at frontend/dist.[/yellow]")
        console.print("[yellow][!] Run 'npm run build' inside frontend/ to build production assets, or run Vite dev server.[/yellow]\n")

    dashboard_app = create_app(db_path=db_path, is_mock=mock)
    uvicorn.run(dashboard_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
