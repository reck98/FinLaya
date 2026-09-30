"""Unit tests for UpstoxInstrumentService get_spot_price method."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from finlaya.broker.upstox_instruments import NIFTY_UNDERLYING_KEY, UpstoxInstrumentService


class DummyMarketQuoteSymbol:
    """Simulates Upstox SDK OpenAPI model without a .get() method."""

    def __init__(self, last_price: float | None):
        self.last_price = last_price

    def to_dict(self):
        return {"last_price": self.last_price}


def test_get_spot_price_success_sdk_model():
    """Verify get_spot_price correctly passes api_version='2.0' and parses SDK model."""
    mock_api_client = MagicMock()
    service = UpstoxInstrumentService(mock_api_client)

    dummy_model = DummyMarketQuoteSymbol(last_price=22714.35)
    mock_resp = MagicMock()
    mock_resp.data = {"NSE_INDEX:Nifty 50": dummy_model}

    with patch("upstox_client.MarketQuoteApi") as MockQuoteApi:
        instance = MockQuoteApi.return_value
        instance.get_full_market_quote.return_value = mock_resp

        spot = service.get_spot_price()
        assert spot == 22714.35

        instance.get_full_market_quote.assert_called_once_with(
            symbol=NIFTY_UNDERLYING_KEY, api_version="2.0"
        )


def test_get_spot_price_success_dict():
    """Verify get_spot_price handles dictionary payloads."""
    mock_api_client = MagicMock()
    service = UpstoxInstrumentService(mock_api_client)

    mock_resp = MagicMock()
    mock_resp.data = {"NSE_INDEX:Nifty 50": {"last_price": 22750.80}}

    with patch("upstox_client.MarketQuoteApi") as MockQuoteApi:
        instance = MockQuoteApi.return_value
        instance.get_full_market_quote.return_value = mock_resp

        spot = service.get_spot_price()
        assert spot == 22750.80


def test_get_spot_price_fallback_to_ltp():
    """Verify fallback to lightweight ltp endpoint if get_full_market_quote returns empty."""
    mock_api_client = MagicMock()
    service = UpstoxInstrumentService(mock_api_client)

    mock_full_resp = MagicMock()
    mock_full_resp.data = {}

    mock_ltp_resp = MagicMock()
    mock_ltp_resp.data = {"NSE_INDEX:Nifty 50": {"last_price": 22720.0}}

    with patch("upstox_client.MarketQuoteApi") as MockQuoteApi:
        instance = MockQuoteApi.return_value
        instance.get_full_market_quote.return_value = mock_full_resp
        instance.ltp.return_value = mock_ltp_resp

        spot = service.get_spot_price()
        assert spot == 22720.0

        instance.get_full_market_quote.assert_called_once_with(
            symbol=NIFTY_UNDERLYING_KEY, api_version="2.0"
        )
        instance.ltp.assert_called_once_with(
            symbol=NIFTY_UNDERLYING_KEY, api_version="2.0"
        )


def test_get_spot_price_fails_closed_on_invalid_data():
    """Verify ValueError is raised if no valid LTP can be extracted from either endpoint."""
    mock_api_client = MagicMock()
    service = UpstoxInstrumentService(mock_api_client)

    mock_full_resp = MagicMock()
    mock_full_resp.data = {}

    mock_ltp_resp = MagicMock()
    mock_ltp_resp.data = {"NSE_INDEX:Nifty 50": {"last_price": 0.0}}

    with patch("upstox_client.MarketQuoteApi") as MockQuoteApi:
        instance = MockQuoteApi.return_value
        instance.get_full_market_quote.return_value = mock_full_resp
        instance.ltp.return_value = mock_ltp_resp

        with pytest.raises(ValueError, match="Could not extract valid spot LTP"):
            service.get_spot_price()
