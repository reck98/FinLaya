"""Technical indicator calculation engine for FinLaya.

All calculations return None (null) if insufficient data points are available.
Fabrication of indicator values is strictly prohibited.
"""

from __future__ import annotations

import math
from typing import Sequence
import numpy as np
from .candles import Candle


def calculate_sma(closes: Sequence[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return float(np.mean(closes[-period:]))


def calculate_ema(closes: Sequence[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    # Exponential Moving Average using standard smoothing multiplier 2 / (period + 1)
    k = 2.0 / (period + 1)
    ema = float(np.mean(closes[:period]))
    for price in closes[period:]:
        ema = (price * k) + (ema * (1.0 - k))
    return float(ema)


def calculate_rsi(closes: Sequence[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    diffs = np.diff(closes)
    gains = np.maximum(diffs, 0.0)
    losses = np.maximum(-diffs, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(diffs)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi)


def calculate_macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float | None, float | None, float | None]:
    """Calculate MACD (macd line, signal line, histogram)."""
    if len(closes) < slow + signal_period:
        return None, None, None

    k_fast = 2.0 / (fast + 1)
    k_slow = 2.0 / (slow + 1)
    k_sig = 2.0 / (signal_period + 1)

    # Compute fast and slow EMAs across the series to get MACD series
    fast_ema = float(np.mean(closes[:fast]))
    for p in closes[fast:]:
        fast_ema = p * k_fast + fast_ema * (1.0 - k_fast)

    # We need a series of MACD values of length at least signal_period
    # Calculate rolling EMAs
    fast_emas = []
    slow_emas = []
    f_val = float(np.mean(closes[:fast]))
    s_val = float(np.mean(closes[:slow]))
    
    # Run through series
    curr_f = closes[0]
    curr_s = closes[0]
    macd_series = []
    for i, p in enumerate(closes):
        if i == 0:
            curr_f = p
            curr_s = p
        else:
            curr_f = p * k_fast + curr_f * (1.0 - k_fast)
            curr_s = p * k_slow + curr_s * (1.0 - k_slow)
        if i >= slow - 1:
            macd_series.append(curr_f - curr_s)

    if len(macd_series) < signal_period:
        return None, None, None

    macd_line = macd_series[-1]
    sig_line = float(np.mean(macd_series[:signal_period]))
    for m in macd_series[signal_period:]:
        sig_line = m * k_sig + sig_line * (1.0 - k_sig)

    hist = macd_line - sig_line
    return float(macd_line), float(sig_line), float(hist)


def calculate_atr(candles: Sequence[Candle], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h = candles[i].high
        l = candles[i].low
        prev_c = candles[i - 1].close
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)

    if len(trs) < period:
        return None

    atr = float(np.mean(trs[:period]))
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return float(atr)


def calculate_vwap(candles: Sequence[Candle]) -> float | None:
    if not candles:
        return None
    cum_pv = sum(((c.high + c.low + c.close) / 3.0) * c.volume for c in candles)
    cum_vol = sum(c.volume for c in candles)
    if cum_vol == 0:
        return float(np.mean([c.close for c in candles]))
    return float(cum_pv / cum_vol)


def calculate_bollinger_bands(
    closes: Sequence[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[float | None, float | None, float | None]:
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    mid = float(np.mean(window))
    std = float(np.std(window))
    upper = mid + (num_std * std)
    lower = mid - (num_std * std)
    return upper, mid, lower


def calculate_technical_indicators(candles: Sequence[Candle]) -> dict[str, float | None]:
    """Compute standard FinLaya indicator set on completed candles."""
    closes = [c.close for c in candles]

    macd_val, macd_sig, macd_hist = calculate_macd(closes)
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(closes)

    return {
        "sma5": calculate_sma(closes, 5),
        "sma10": calculate_sma(closes, 10),
        "sma20": calculate_sma(closes, 20),
        "ema5": calculate_ema(closes, 5),
        "ema9": calculate_ema(closes, 9),
        "ema20": calculate_ema(closes, 20),
        "rsi14": calculate_rsi(closes, 14),
        "macd": macd_val,
        "macd_signal": macd_sig,
        "macd_histogram": macd_hist,
        "atr14": calculate_atr(candles, 14),
        "vwap": calculate_vwap(candles),
        "bb_upper": bb_upper,
        "bb_middle": bb_mid,
        "bb_lower": bb_lower,
    }
