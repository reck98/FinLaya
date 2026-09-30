"""Unit tests for historical candle fetching, seeding, indicator completeness, and depth quote parsing."""

from unittest.mock import MagicMock
import pytest

from finlaya.broker.upstox_instruments import UpstoxInstrumentService, NIFTY_UNDERLYING_KEY
from finlaya.broker.upstox_market_data import UpstoxMarketDataFeed
from finlaya.laya.model import LayaDecisionModel
from finlaya.market.candles import Candle, CandleEngine
from finlaya.market.indicators import calculate_technical_indicators
from finlaya.market.state import MarketDataCache


def test_laya_model_extracts_probabilities_and_answer_confidence():
    """Verify LayaDecisionModel extracts choice softmax probability instead of raw policy confidence."""
    model = LayaDecisionModel()

    # Case 1: probabilities dict present with BUY and SELL
    raw_resp_choice = {
        "answers": {
            "trading_action": {
                "type": "choice",
                "choice": "SELL",
                "probabilities": {
                    "BUY": 0.4878,
                    "SELL": 0.5122,
                },
                "confidence": 0.0004,
                "answer_confidence": 0.5122,
            }
        }
    }
    decision = model._parse_response(raw_resp_choice)
    assert decision.action == "SELL"
    assert decision.confidence == pytest.approx(0.5122)

    # Case 2: probabilities with lowercase keys
    raw_resp_lower = {
        "answers": {
            "trading_action": {
                "choice": "BUY",
                "probabilities": {
                    "buy": 0.5432,
                    "sell": 0.4568,
                },
                "confidence": 0.0001,
            }
        }
    }
    decision_lower = model._parse_response(raw_resp_lower)
    assert decision_lower.action == "BUY"
    assert decision_lower.confidence == pytest.approx(0.5432)

    # Case 3: fallback to answer_confidence
    raw_resp_ans_conf = {
        "answers": {
            "trading_action": {
                "choice": "HOLD",
                "answer_confidence": 0.7788,
                "confidence": 0.0002,
            }
        }
    }
    decision_ans = model._parse_response(raw_resp_ans_conf)
    assert decision_ans.action == "HOLD"
    assert decision_ans.confidence == pytest.approx(0.7788)


def test_historical_candle_fetching_and_indicator_completeness():
    """Verify that 60 seeded candles produce 100% non-null values for all 14 technical indicators."""
    mock_api_client = MagicMock()
    service = UpstoxInstrumentService(mock_api_client)

    # Simulate 60 historical 1-minute candles
    mock_candles_data = []
    base_price = 22700.0
    for i in range(60):
        minute = f"{i:02d}"
        mock_candles_data.append([
            f"2026-09-30T10:{minute}:00+05:30",
            base_price + i,
            base_price + i + 2,
            base_price + i - 1,
            base_price + i + 1,
            1000 + i * 10,
            0,
        ])
    # Upstox returns newest first
    mock_candles_data.reverse()

    mock_resp = MagicMock()
    mock_resp.data.candles = mock_candles_data

    mock_history_api = MagicMock()
    mock_history_api.get_intra_day_candle_data.return_value = mock_resp

    with pytest.MonkeyPatch.context() as mp:
        import upstox_client
        mp.setattr(upstox_client, "HistoryApi", lambda client: mock_history_api)

        candles = service.fetch_historical_candles(NIFTY_UNDERLYING_KEY, min_candles=60)
        assert len(candles) == 60
        # Assert chronological order (oldest first)
        assert candles[0].timestamp < candles[-1].timestamp

        # Seed into CandleEngine
        engine = CandleEngine(max_candles=60)
        engine.seed_historical_candles(candles)
        seeded = engine.get_completed_candles()
        assert len(seeded) == 60

        # Calculate indicators and verify NO NULLS
        indicators = calculate_technical_indicators(seeded)
        assert len(indicators) == 15

        null_keys = [k for k, v in indicators.items() if v is None]
        assert null_keys == [], f"Expected zero null indicators, found nulls in: {null_keys}"
        assert isinstance(indicators["sma5"], float)
        assert isinstance(indicators["sma10"], float)
        assert isinstance(indicators["sma20"], float)
        assert isinstance(indicators["ema5"], float)
        assert isinstance(indicators["ema9"], float)
        assert isinstance(indicators["ema20"], float)
        assert isinstance(indicators["rsi14"], float)
        assert isinstance(indicators["macd"], float)
        assert isinstance(indicators["macd_signal"], float)
        assert isinstance(indicators["macd_histogram"], float)
        assert isinstance(indicators["atr14"], float)
        assert isinstance(indicators["vwap"], float)
        assert isinstance(indicators["bb_upper"], float)
        assert isinstance(indicators["bb_middle"], float)
        assert isinstance(indicators["bb_lower"], float)


def test_protobuf_depth_parsing_bid_ask():
    """Verify Upstox V3 protobuf fields (bidP/bidQ/askP/askQ) are mapped properly to InstrumentQuote."""
    cache = MarketDataCache()
    feed = UpstoxMarketDataFeed(MagicMock(), cache=cache)

    protobuf_payload = {
        "marketFF": {
            "ltpc": {"ltp": 125.5, "cp": 120.0},
            "vtt": 50000,
            "oi": 12000,
            "marketLevel": {
                "bidAskQuote": [
                    {
                        "bidP": 125.4,
                        "bidQ": 1500,
                        "askP": 125.6,
                        "askQ": 2000,
                    }
                ]
            },
            "marketOHLC": {
                "ohlc": [
                    {"interval": "1d", "open": 110.0, "high": 130.0, "low": 105.0, "close": 125.5}
                ]
            }
        }
    }

    message = {
        "feeds": {
            "NSE_FO|12345": {
                "fullFeed": protobuf_payload
            }
        }
    }

    feed._on_message(message)

    quote = cache.get_quote("NSE_FO|12345")
    assert quote is not None
    assert quote.ltp == 125.5
    assert quote.bid == 125.4
    assert quote.bid_qty == 1500
    assert quote.ask == 125.6
    assert quote.ask_qty == 2000
