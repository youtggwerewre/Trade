from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import pandas as pd

from indicators import ema, rsi, macd, atr, swing_levels
import config


@dataclass
class Signal:
    direction: str          # "BUY" or "SELL"
    entry: float
    zone_low: float
    zone_high: float
    stop_loss: float
    tp1: float
    tp2: float
    confidence: str          # "Low" / "Medium" / "High"
    rr: float
    timeframe: str
    hold_time: str
    score: int


def session_note() -> str:
    """Real UTC-clock-based liquidity note, not a fabricated guess."""
    hour = datetime.now(timezone.utc).hour
    if 0 <= hour < 7:
        return "Asia session — thinner liquidity, expect slippage ⚠️"
    if 7 <= hour < 12:
        return "London session — liquidity picking up"
    if 12 <= hour < 16:
        return "London/New York overlap — highest liquidity window"
    if 16 <= hour < 21:
        return "New York session — active liquidity"
    return "Late NY / pre-Asia — liquidity thinning"


def analyze(df: pd.DataFrame, timeframe: str) -> Optional[Signal]:
    if len(df) < 60:
        return None  # not enough candles yet for a reliable read

    close = df["close"]
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    long_period = min(200, len(df) - 1)
    ema_long = ema(close, long_period)
    rsi14 = rsi(close, 14)
    _, _, hist = macd(close)
    atr14 = atr(df, 14)
    swing_high, swing_low = swing_levels(df, config.SWING_LOOKBACK)

    price = close.iloc[-1]
    last_atr = atr14.iloc[-1]
    if pd.isna(last_atr) or last_atr <= 0:
        return None

    bull_votes = 0
    bear_votes = 0

    # 1. Trend: EMA stack
    if ema20.iloc[-1] > ema50.iloc[-1] > ema_long.iloc[-1]:
        bull_votes += 1
    elif ema20.iloc[-1] < ema50.iloc[-1] < ema_long.iloc[-1]:
        bear_votes += 1

    # 2. Momentum: RSI
    if rsi14.iloc[-1] > 55:
        bull_votes += 1
    elif rsi14.iloc[-1] < 45:
        bear_votes += 1

    # 3. Momentum: MACD histogram
    if hist.iloc[-1] > 0:
        bull_votes += 1
    elif hist.iloc[-1] < 0:
        bear_votes += 1

    # 4. Structure: price vs recent swing range midpoint
    mid = (swing_high + swing_low) / 2
    if price > mid:
        bull_votes += 1
    elif price < mid:
        bear_votes += 1

    if bull_votes == bear_votes:
        return None  # genuinely no edge — this is why the bot won't spam every cycle

    direction = "BUY" if bull_votes > bear_votes else "SELL"
    score = max(bull_votes, bear_votes)
    confidence = {2: "Low", 3: "Medium", 4: "High"}.get(score, "Low")

    buffer = last_atr * config.ATR_SL_BUFFER
    entry = price
    zone_low, zone_high = entry - last_atr * 0.15, entry + last_atr * 0.15

    if direction == "BUY":
        stop_loss = swing_low - buffer
        risk = entry - stop_loss
        tp1 = entry + risk * config.RISK_REWARD_TP1
        tp2 = entry + risk * config.RISK_REWARD_TP2
    else:
        stop_loss = swing_high + buffer
        risk = stop_loss - entry
        tp1 = entry - risk * config.RISK_REWARD_TP1
        tp2 = entry - risk * config.RISK_REWARD_TP2

    if risk <= 0:
        return None

    rr = round(abs(tp1 - entry) / risk, 1)
    hold_time = config.HOLD_TIME_MAP.get(timeframe, "N/A")

    return Signal(
        direction=direction, entry=round(entry, 2),
        zone_low=round(zone_low, 2), zone_high=round(zone_high, 2),
        stop_loss=round(stop_loss, 2), tp1=round(tp1, 2), tp2=round(tp2, 2),
        confidence=confidence, rr=rr, timeframe=timeframe,
        hold_time=hold_time, score=score,
    )
