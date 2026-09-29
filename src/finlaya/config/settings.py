"""Strongly typed application configuration and settings loader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import BaseModel, Field, field_validator


class ProjectConfig(BaseModel):
    name: str = "FinLaya"
    timezone: str = "Asia/Kolkata"


class TradingConfig(BaseModel):
    start_time: str = "09:27:00"
    force_exit_time: str = "15:13:00"
    lots: int = Field(default=1, ge=1)
    expected_lot_size: int = Field(default=65, ge=1)
    enforce_expected_lot_size: bool = True
    strike_step: int = Field(default=50, ge=1)
    lot_size_source: Literal["broker", "configured"] = "broker"


class StrategyConfig(BaseModel):
    decision_interval_seconds: float = Field(default=0.5, gt=0.0)
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)


class MarketDataConfig(BaseModel):
    candle_interval: str = "1minute"
    historical_candles: int = Field(default=6, ge=1)
    max_staleness_seconds: float = Field(default=2.0, gt=0.0)


class LayaConfig(BaseModel):
    model: str = "convaiinnovations/laya"
    device: str = "auto"
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)


class PaperTradingConfig(BaseModel):
    enabled: bool = True
    price_fallback: Literal["ltp", "bid_ask"] = "ltp"


class DatabaseConfig(BaseModel):
    path: str = "data/finlaya.db"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    directory: str = "data/logs"


class UpstoxConfig(BaseModel):
    access_token: str | None = None
    api_key: str | None = None
    api_secret: str | None = None


class AppConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    market_data: MarketDataConfig = Field(default_factory=MarketDataConfig)
    laya: LayaConfig = Field(default_factory=LayaConfig)
    paper_trading: PaperTradingConfig = Field(default_factory=PaperTradingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    upstox: UpstoxConfig = Field(default_factory=UpstoxConfig)


def _load_dotenv(env_path: Path | None = None) -> None:
    """Simple .env parser without external dependencies."""
    if env_path is None:
        env_path = Path(".env")
    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v


def load_config(config_path: str | Path | None = None, env_path: str | Path | None = None) -> AppConfig:
    """Load and merge configuration from config.yaml and .env / environment variables."""
    _load_dotenv(Path(env_path) if env_path else None)

    if config_path is None:
        config_path = Path("config/config.yaml")
    else:
        config_path = Path(config_path)

    raw_data: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                raw_data = loaded

    # Overlay environment secrets for Upstox
    upstox_env = {
        "access_token": os.getenv("UPSTOX_ACCESS_TOKEN"),
        "api_key": os.getenv("UPSTOX_API_KEY"),
        "api_secret": os.getenv("UPSTOX_API_SECRET"),
    }
    raw_upstox = raw_data.get("upstox", {})
    if not isinstance(raw_upstox, dict):
        raw_upstox = {}
    for k, v in upstox_env.items():
        if v:
            raw_upstox[k] = v
    raw_data["upstox"] = raw_upstox

    return AppConfig.model_validate(raw_data)
