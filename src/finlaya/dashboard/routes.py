"""Read-only REST API endpoints for FinLaya dashboard."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/health")
async def get_health(request: Request) -> dict[str, Any]:
    state = request.app.state.dashboard_state
    return state.health


@router.get("/session")
async def get_session(request: Request) -> dict[str, Any]:
    state = request.app.state.dashboard_state
    return state.session


@router.get("/market")
async def get_market(request: Request) -> dict[str, Any]:
    state = request.app.state.dashboard_state
    return state.market


@router.get("/position")
async def get_position(request: Request) -> dict[str, Any]:
    state = request.app.state.dashboard_state
    return state.position


@router.get("/pnl")
async def get_pnl(request: Request) -> dict[str, Any]:
    state = request.app.state.dashboard_state
    return {
        "realized": state.pnl["realized"],
        "unrealized": state.pnl["unrealized"],
        "total": state.pnl["total"],
    }


@router.get("/pnl/history")
async def get_pnl_history(request: Request) -> list[dict[str, Any]]:
    state = request.app.state.dashboard_state
    return state.pnl["history"]


@router.get("/laya/recent")
async def get_recent_decisions(request: Request) -> list[dict[str, Any]]:
    state = request.app.state.dashboard_state
    return list(state.recent_decisions)


@router.get("/orders/recent")
async def get_recent_orders(request: Request) -> list[dict[str, Any]]:
    state = request.app.state.dashboard_state
    return list(state.recent_orders)


@router.get("/events/recent")
async def get_recent_events(request: Request) -> list[dict[str, Any]]:
    state = request.app.state.dashboard_state
    return list(state.recent_events)


@router.get("/stats")
async def get_stats(request: Request) -> dict[str, Any]:
    state = request.app.state.dashboard_state
    return state.stats


@router.get("/snapshot")
async def get_snapshot(request: Request) -> dict[str, Any]:
    state = request.app.state.dashboard_state
    return state.get_snapshot()
