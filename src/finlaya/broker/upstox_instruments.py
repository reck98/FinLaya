"""Upstox option contract discovery, dynamic expiry verification, and lot size validation."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
import upstox_client
from upstox_client.rest import ApiException

from finlaya.logging.logger import FinLayaLogger, LogEvent, get_logger
from finlaya.utils.time import IST, now_ist
from finlaya.broker.base import (
    ExpiryResolutionError,
    InstrumentMetadata,
    LotSizeMismatchError,
    NiftyExpiryDayError,
)

logger = get_logger("upstox_instruments")

NIFTY_UNDERLYING_KEY = "NSE_INDEX|Nifty 50"


class UpstoxInstrumentService:
    """Service to discover option contracts and enforce safety checks."""

    def __init__(self, api_client: upstox_client.ApiClient):
        self.api_client = api_client

    def fetch_all_nifty_contracts(self) -> list[dict[str, Any]]:
        """Fetch all option contracts for NIFTY from Upstox API v2."""
        options_api = upstox_client.OptionsApi(self.api_client)
        try:
            resp = options_api.get_option_contracts(instrument_key=NIFTY_UNDERLYING_KEY)
            data = resp.data if hasattr(resp, "data") else []
            contracts = []
            for item in data:
                d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
                contracts.append(d)
            if not contracts:
                raise ExpiryResolutionError("Upstox returned 0 option contracts for NIFTY. Failing closed.")
            return contracts
        except ApiException as e:
            logger.error(f"Failed to fetch option contracts: status={e.status}, body={e.body}", LogEvent.ERROR)
            raise ExpiryResolutionError(f"Upstox API error fetching contracts: {e}") from e
        except Exception as e:
            if isinstance(e, ExpiryResolutionError):
                raise
            logger.error(f"Unexpected error fetching contracts: {e}", LogEvent.ERROR)
            raise ExpiryResolutionError(f"Cannot resolve contracts: {e}") from e

    def get_expiry_dates(self, contracts: list[dict[str, Any]]) -> list[str]:
        """Extract and sort all unique expiry dates (YYYY-MM-DD) from contract metadata."""
        expiries = set()
        for c in contracts:
            expiry_val = c.get("expiry")
            if expiry_val:
                # Format can be 'YYYY-MM-DD' or datetime
                if isinstance(expiry_val, datetime):
                    expiries.add(expiry_val.strftime("%Y-%m-%d"))
                elif isinstance(expiry_val, str):
                    expiries.add(expiry_val[:10])
        sorted_expiries = sorted(list(expiries))
        if not sorted_expiries:
            raise ExpiryResolutionError("No valid expiry dates found in NIFTY contract metadata. Failing closed.")
        return sorted_expiries

    def verify_not_expiry_day(self, sorted_expiries: list[str], today: date | None = None) -> None:
        """Fail closed if today is a NIFTY expiry day."""
        current_date = today or now_ist().date()
        today_str = current_date.strftime("%Y-%m-%d")

        logger.info(
            f"Checking NIFTY expiry for today={today_str}. Available expiries: {sorted_expiries[:5]}...",
            LogEvent.EXPIRY_CHECK,
        )

        if today_str in sorted_expiries:
            logger.error(
                f"Today ({today_str}) is an authoritative NIFTY option expiry day. Trading is prohibited.",
                LogEvent.EXPIRY_DAY_ABORT,
            )
            raise NiftyExpiryDayError(f"NIFTY_EXPIRY_DAY: Today ({today_str}) is an expiry day. Strategy aborted.")

        logger.info(f"Verified today ({today_str}) is NOT a NIFTY expiry day.", LogEvent.EXPIRY_CHECK)

    def select_target_expiry(self, sorted_expiries: list[str], today: date | None = None) -> str:
        """Select the earliest future expiry strictly after today."""
        current_date = today or now_ist().date()
        today_str = current_date.strftime("%Y-%m-%d")

        future_expiries = [e for e in sorted_expiries if e > today_str]
        if not future_expiries:
            raise ExpiryResolutionError("No future NIFTY expiry dates found. Failing closed.")

        selected = future_expiries[0]
        logger.info(f"Selected nearest future NIFTY expiry: {selected}", LogEvent.EXPIRY_CHECK)
        return selected

    def discover_contracts(
        self,
        contracts: list[dict[str, Any]],
        strike: int,
        target_expiry: str,
        expected_lot_size: int | None = 65,
        enforce_lot_size: bool = True,
    ) -> tuple[InstrumentMetadata, InstrumentMetadata]:
        """Discover exact CE and PE contracts for selected strike and expiry."""
        ce_match: dict[str, Any] | None = None
        pe_match: dict[str, Any] | None = None

        for c in contracts:
            c_expiry = str(c.get("expiry", ""))[:10]
            if c_expiry != target_expiry:
                continue

            c_strike = float(c.get("strike_price", 0.0))
            if int(round(c_strike)) != strike:
                continue

            itype = str(c.get("instrument_type", "")).upper()
            if itype == "CE":
                ce_match = c
            elif itype == "PE":
                pe_match = c

        if not ce_match or not pe_match:
            missing = []
            if not ce_match:
                missing.append("CE")
            if not pe_match:
                missing.append("PE")
            raise ExpiryResolutionError(
                f"Could not discover {missing} contracts for strike={strike}, expiry={target_expiry}. Failing closed."
            )

        # Validate lot sizes
        broker_ce_lot = int(ce_match.get("lot_size", 0))
        broker_pe_lot = int(pe_match.get("lot_size", 0))

        if broker_ce_lot != broker_pe_lot or broker_ce_lot <= 0:
            raise LotSizeMismatchError(f"Inconsistent lot sizes: CE={broker_ce_lot}, PE={broker_pe_lot}")

        broker_lot = broker_ce_lot
        logger.info(
            f"Broker reported lot_size={broker_lot}, expected_lot_size={expected_lot_size}",
            LogEvent.LOT_SIZE_VERIFIED,
        )

        if enforce_lot_size and expected_lot_size is not None:
            if broker_lot != expected_lot_size:
                msg = (
                    f"Lot size mismatch: Broker reported {broker_lot}, but configuration expected {expected_lot_size}. "
                    "Aborting for safety to prevent incorrect contract sizing."
                )
                logger.error(msg, LogEvent.ERROR)
                raise LotSizeMismatchError(msg)

        ce_meta = InstrumentMetadata(
            instrument_key=str(ce_match["instrument_key"]),
            trading_symbol=str(ce_match.get("trading_symbol", "")),
            strike_price=float(ce_match["strike_price"]),
            expiry=target_expiry,
            instrument_type="CE",
            lot_size=broker_lot,
            tick_size=float(ce_match.get("tick_size", 0.05)),
        )

        pe_meta = InstrumentMetadata(
            instrument_key=str(pe_match["instrument_key"]),
            trading_symbol=str(pe_match.get("trading_symbol", "")),
            strike_price=float(pe_match["strike_price"]),
            expiry=target_expiry,
            instrument_type="PE",
            lot_size=broker_lot,
            tick_size=float(pe_match.get("tick_size", 0.05)),
        )

        logger.info(
            f"Discovered CE: key={ce_meta.instrument_key}, symbol={ce_meta.trading_symbol}, lot={ce_meta.lot_size}",
            LogEvent.INSTRUMENT_SELECTION,
        )
        logger.info(
            f"Discovered PE: key={pe_meta.instrument_key}, symbol={pe_meta.trading_symbol}, lot={pe_meta.lot_size}",
            LogEvent.INSTRUMENT_SELECTION,
        )

        return ce_meta, pe_meta

    def get_spot_price(self) -> float:
        """Fetch current live NIFTY 50 spot price from Upstox REST API."""
        quote_api = upstox_client.MarketQuoteApi(self.api_client)
        try:
            resp = quote_api.get_full_market_quote(NIFTY_UNDERLYING_KEY)
            data = resp.data if hasattr(resp, "data") else {}
            # Upstox returns keys with colon or pipe format
            nifty_data = None
            if hasattr(data, "to_dict"):
                data = data.to_dict()
            for k, v in data.items():
                if "nifty 50" in k.lower() or "nifty_50" in k.lower() or "nse_index" in k.lower():
                    nifty_data = v
                    break

            if not nifty_data and data:
                # If single item dictionary
                nifty_data = next(iter(data.values()))

            if nifty_data:
                ltp = float(nifty_data.get("last_price", 0.0))
                if ltp > 0:
                    return ltp

            raise ValueError(f"Could not extract valid spot LTP from response: {data}")
        except Exception as e:
            logger.error(f"Failed to fetch NIFTY spot price: {e}", LogEvent.ERROR)
            raise
