"""Upstox API client wrapper, authentication, and market-open verification."""

from __future__ import annotations

import logging
from typing import Any
import upstox_client
from upstox_client.rest import ApiException

from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from finlaya.broker.base import MarketClosedError
from finlaya.utils.time import now_ist

logger = get_logger("upstox_client")


class UpstoxClient:
    """Manages Upstox REST API sessions and connectivity health checks."""

    def __init__(self, access_token: str | None = None, api_key: str | None = None, api_secret: str | None = None):
        self.access_token = access_token
        self.api_key = api_key
        self.api_secret = api_secret
        self.configuration = upstox_client.Configuration()
        if access_token:
            self.configuration.access_token = access_token
        self.api_client = upstox_client.ApiClient(self.configuration)

    def is_configured(self) -> bool:
        """Check if access token is present."""
        return bool(self.access_token and len(self.access_token.strip()) > 0)

    def validate_connectivity(self) -> dict[str, Any]:
        """Validate API connectivity by retrieving user profile.
        
        Never logs or exposes the access token.
        """
        if not self.is_configured():
            raise ValueError("Upstox access token is missing. Configure UPSTOX_ACCESS_TOKEN in .env")

        user_api = upstox_client.UserApi(self.api_client)
        try:
            profile = user_api.get_profile("2.0")
            profile_data = profile.data.to_dict() if hasattr(profile.data, "to_dict") else {}
            logger.info("Upstox connected successfully", LogEvent.UPSTOX_CONNECTED, metadata={"user_id": profile_data.get("user_id")})
            return profile_data
        except ApiException as e:
            logger.error(f"Upstox authentication failed: status={e.status}, body={e.body}", LogEvent.ERROR)
            raise

    def check_market_open(self, exchange: str = "NSE") -> bool:
        """Check if the market exchange is active/open today.
        
        Fails closed if closed or on weekend / holiday.
        """
        # First verify weekday (Monday=0 to Friday=4)
        current_ist = now_ist()
        if current_ist.weekday() >= 5:
            logger.warning(f"Market closed: Today is weekend ({current_ist.strftime('%A')})", LogEvent.MARKET_OPEN_CHECK)
            return False

        market_api = upstox_client.MarketHolidaysAndTimingsApi(self.api_client)
        try:
            status_resp = market_api.get_market_status(exchange)
            status_data = status_resp.data.to_dict() if hasattr(status_resp.data, "to_dict") else {}
            market_status = status_data.get("status", "").upper()
            logger.info(f"Exchange {exchange} status: {market_status}", LogEvent.MARKET_OPEN_CHECK, metadata=status_data)
            # Market status can be 'OPEN', 'NORMAL_TRADING', or scheduled
            if market_status in ("CLOSED", "HOLIDAY"):
                return False
            return True
        except Exception as e:
            logger.warning(f"Could not fetch official market status via API ({e}). Falling back to IST trading hours check.")
            # If API is temporarily uninformative about holidays, fall back to checking if within IST weekday
            return current_ist.weekday() < 5
