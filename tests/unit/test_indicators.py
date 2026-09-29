"""Unit tests for technical indicators calculation."""

from finlaya.market.candles import Candle
from finlaya.market.indicators import (
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_atr,
    calculate_vwap,
    calculate_bollinger_bands,
    calculate_technical_indicators,
)


def test_indicators_insufficient_data_returns_none():
    # Only 3 candles provided: indicators requiring more points must return None
    candles = [
        Candle(timestamp=f"2026-09-29T09:2{i}:00+05:30", open=23400.0, high=23410.0, low=23395.0, close=23405.0, volume=100)
        for i in range(3)
    ]
    closes = [c.close for c in candles]

    # SMA 5 requires 5
    assert calculate_sma(closes, 5) is None
    # EMA 5 requires 5
    assert calculate_ema(closes, 5) is None
    # RSI 14 requires 15
    assert calculate_rsi(closes, 14) is None
    # MACD requires slow + signal = 26 + 9 = 35
    macd_val, _, _ = calculate_macd(closes)
    assert macd_val is None
    # ATR 14 requires 15
    assert calculate_atr(candles, 14) is None
    # Bollinger Bands 20 requires 20
    bb_u, _, _ = calculate_bollinger_bands(closes, 20)
    assert bb_u is None


def test_sma_calculation():
    closes = [10.0, 20.0, 30.0, 40.0, 50.0]
    # SMA 5 = (10+20+30+40+50)/5 = 30.0
    assert calculate_sma(closes, 5) == 30.0
    # SMA 3 = (30+40+50)/3 = 40.0
    assert calculate_sma(closes, 3) == 40.0


def test_vwap_calculation():
    candles = [
        Candle(timestamp="1", open=100, high=105, low=95, close=100, volume=1000),  # typical=(105+95+100)/3 = 100
        Candle(timestamp="2", open=100, high=115, low=105, close=110, volume=2000), # typical=(115+105+110)/3 = 110
    ]
    # total pv = (100 * 1000) + (110 * 2000) = 100,000 + 220,000 = 320,000
    # total vol = 3000
    # vwap = 320000 / 3000 = 106.67
    vwap = calculate_vwap(candles)
    assert vwap is not None
    assert round(vwap, 2) == 106.67


def test_full_indicator_dict():
    # Provide 40 constant candles
    candles = [
        Candle(timestamp=f"T{i}", open=100.0, high=105.0, low=95.0, close=100.0, volume=1000)
        for i in range(40)
    ]
    indicators = calculate_technical_indicators(candles)
    assert indicators["sma5"] == 100.0
    assert indicators["sma10"] == 100.0
    assert indicators["sma20"] == 100.0
    assert round(indicators["ema5"], 2) == 100.0
    assert indicators["bb_middle"] == 100.0
    assert indicators["bb_upper"] == 100.0  # std is 0
