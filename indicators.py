import pandas as pd
import numpy as np


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def swing_levels(df: pd.DataFrame, lookback: int = 50, order: int = 3):
    """Simple pivot-based swing high/low over the last `lookback` candles."""
    recent = df.tail(lookback).reset_index(drop=True)
    highs, lows = [], []
    for i in range(order, len(recent) - order):
        window = recent.iloc[i - order:i + order + 1]
        if recent["high"][i] == window["high"].max():
            highs.append(recent["high"][i])
        if recent["low"][i] == window["low"].min():
            lows.append(recent["low"][i])
    swing_high = max(highs) if highs else recent["high"].max()
    swing_low = min(lows) if lows else recent["low"].min()
    return swing_high, swing_low
