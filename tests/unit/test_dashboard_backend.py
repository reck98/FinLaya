"""Unit tests for FinLaya Real-Time Dashboard backend, state manager, and IPC."""

import asyncio
import os
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from finlaya.dashboard.app import create_app
from finlaya.dashboard.state import DashboardStateManager
from finlaya.dashboard.telemetry import TelemetryBroadcaster
from finlaya.dashboard.mock import MockEventGenerator
from finlaya.dashboard.websocket import WebSocketManager


@pytest.fixture
def test_app():
    return create_app(db_path=":memory:", is_mock=False)


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


def test_api_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "bot_status" in data
    assert "database_status" in data


def test_api_session_and_market_endpoints(client):
    res_session = client.get("/api/session")
    assert res_session.status_code == 200
    assert "status" in res_session.json()

    res_market = client.get("/api/market")
    assert res_market.status_code == 200
    assert "nifty_spot" in res_market.json()


def test_api_position_and_pnl_endpoints(client):
    res_pos = client.get("/api/position")
    assert res_pos.status_code == 200
    assert res_pos.json()["side"] == "FLAT"

    res_pnl = client.get("/api/pnl")
    assert res_pnl.status_code == 200
    assert "total" in res_pnl.json()


def test_api_snapshot_endpoint(client):
    res = client.get("/api/snapshot")
    assert res.status_code == 200
    data = res.json()
    assert "session" in data
    assert "market" in data
    assert "position" in data
    assert "pnl" in data
    assert "stats" in data
    assert "health" in data


def test_dashboard_state_manager_events():
    sm = DashboardStateManager(db_path=":memory:", is_mock=False)

    # 1. Market update
    sm.apply_event("market_update", {
        "nifty_spot": 23450.50,
        "ce_ltp": 140.0,
        "pe_ltp": 115.0,
        "timestamp": "2026-09-29T09:27:01+05:30",
    })
    assert sm.market["nifty_spot"] == 23450.50
    assert sm.market["ce_ltp"] == 140.0
    assert sm.health["market_data_status"] == "LIVE"

    # 2. Laya Decision update
    sm.apply_event("laya_decision", {
        "action": "BUY",
        "confidence": 0.725,
        "position_before": "FLAT",
        "inference_latency_ms": 175.5,
        "accepted": True,
        "timestamp": "2026-09-29T09:27:01+05:30",
    })
    assert sm.latest_decision["action"] == "BUY"
    assert sm.stats["laya_calls"] == 1
    assert sm.stats["buy_decisions"] == 1
    assert sm.stats["accepted_signals"] == 1
    assert sm.stats["avg_latency_ms"] == 175.5

    # 3. Position update
    sm.apply_event("position_update", {
        "instrument": "NIFTY26OCT23450CE",
        "side": "LONG_CE",
        "quantity": 65,
        "entry_price": 140.0,
        "current_price": 145.0,
        "unrealized_pnl": 325.0,
        "realized_pnl": 0.0,
        "total_pnl": 325.0,
    })
    assert sm.position["side"] == "LONG_CE"
    assert sm.pnl["unrealized"] == 325.0
    assert sm.pnl["total"] == 325.0

    # 4. Heartbeat & Liveness
    sm.apply_event("heartbeat", {
        "status": "RUNNING",
        "session_id": 42,
        "timestamp": "2026-09-29T09:27:01+05:30",
    })
    assert sm.health["bot_status"] == "RUNNING"
    assert sm.session["id"] == 42
    assert sm.check_liveness(timeout_seconds=5.0) is True

    # Simulate timeout
    sm.health["last_heartbeat_time"] = time.monotonic() - 10.0
    assert sm.check_liveness(timeout_seconds=3.0) is False
    assert sm.health["bot_status"] == "OFFLINE"


@pytest.mark.asyncio
async def test_mock_event_generator():
    sm = DashboardStateManager(db_path=":memory:", is_mock=True)
    wm = WebSocketManager()
    gen = MockEventGenerator(state_manager=sm, ws_manager=wm)

    await gen.start()
    assert sm.is_mock is True
    assert sm.session["selected_strike"] == 23450

    # Wait for at least one simulation tick
    await asyncio.sleep(0.6)
    assert sm.stats["laya_calls"] >= 1
    assert sm.market["nifty_spot"] > 0

    await gen.stop()


def test_telemetry_broadcaster_file_and_udp(tmp_path):
    hb_file = tmp_path / "runtime" / "heartbeat.json"
    broadcaster = TelemetryBroadcaster(port=8769, heartbeat_path=hb_file)

    broadcaster.record_heartbeat(session_id=123, status="RUNNING")
    assert hb_file.exists()

    broadcaster.emit("test_event", {"key": "val"})
    broadcaster.close()
