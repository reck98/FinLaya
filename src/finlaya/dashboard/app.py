"""FastAPI application factory and lifecycle management for FinLaya Dashboard."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .state import DashboardStateManager
from .websocket import WebSocketManager
from .ipc import IPCReceiver
from .mock import MockEventGenerator
from .routes import router as api_router

logger = logging.getLogger(__name__)


def create_app(
    db_path: str = "data/finlaya.db",
    is_mock: bool = False,
    static_dir: str | Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI dashboard application."""
    state_manager = DashboardStateManager(db_path=db_path, is_mock=is_mock)
    ws_manager = WebSocketManager()
    ipc_receiver = IPCReceiver(state_manager=state_manager, ws_manager=ws_manager)
    mock_generator = MockEventGenerator(state_manager=state_manager, ws_manager=ws_manager)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # 1. Hydrate state from SQLite
        await state_manager.hydrate_from_sqlite()

        # 2. Start Telemetry Receiver or Mock Generator
        if is_mock:
            logger.info("Initializing in MOCK mode.")
            await mock_generator.start()
        else:
            logger.info("Initializing live IPC receiver.")
            await ipc_receiver.start()

        yield

        # Shutdown
        if is_mock:
            await mock_generator.stop()
        else:
            await ipc_receiver.stop()

    app = FastAPI(
        title="FinLaya Trading Dashboard",
        description="Professional real-time paper-trading observability interface for FinLaya",
        lifespan=lifespan,
    )

    # Attach shared instances to app state
    app.state.dashboard_state = state_manager
    app.state.ws_manager = ws_manager
    app.state.is_mock = is_mock

    # Enable CORS for local development (e.g. Vite dev server on localhost:5173)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount REST routes
    app.include_router(api_router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket, initial_snapshot=state_manager.get_snapshot())
        try:
            while True:
                # Keep socket alive and accept ping/pong messages
                await websocket.receive_text()
        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket)
        except Exception:
            await ws_manager.disconnect(websocket)

    # Mount static frontend assets
    resolved_static_dir = None
    if static_dir and Path(static_dir).exists():
        resolved_static_dir = Path(static_dir)
    elif Path("frontend/dist").exists():
        resolved_static_dir = Path("frontend/dist")
    elif (Path(__file__).parent / "static").exists():
        resolved_static_dir = Path(__file__).parent / "static"

    if resolved_static_dir:
        # Mount assets under /assets or static files
        if (resolved_static_dir / "assets").exists():
            app.mount("/assets", StaticFiles(directory=resolved_static_dir / "assets"), name="assets")
        app.mount("/static", StaticFiles(directory=resolved_static_dir), name="static")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # Don't intercept API or WS
            if full_path.startswith("api/") or full_path == "ws":
                return HTMLResponse(status_code=404, content="Not Found")
            file_path = resolved_static_dir / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            index_path = resolved_static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return HTMLResponse(content="<h1>FinLaya Dashboard</h1><p>Frontend build index.html not found.</p>")
    else:
        @app.get("/")
        async def root():
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>FinLaya Dashboard</title></head>
                <body style="background:#09090b;color:#f4f4f5;font-family:sans-serif;padding:40px;">
                    <h2>FinLaya Real-Time Trading Dashboard Backend</h2>
                    <p>FastAPI Backend is running on <code>http://127.0.0.1:8765</code>.</p>
                    <p>API Snapshot: <a style="color:#10b981;" href="/api/snapshot">/api/snapshot</a></p>
                    <p>WebSocket: <code>ws://127.0.0.1:8765/ws</code></p>
                    <p><em>To launch the React frontend in dev mode, run <code>npm run dev</code> inside <code>frontend/</code>.</em></p>
                </body>
                </html>
                """
            )

    return app
