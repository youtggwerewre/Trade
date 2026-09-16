"""
Quick offline check — generates fake candles (no network/API key needed) and
runs them through the real signal engine + formatter, so you can see the
exact message the bot will post before wiring up live data.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

from signal_engine import analyze
from formatter import format_signal
from lot_size import calculate_lot_size


def synthetic_candles(n=300, start_price=4180.0, seed=7, drift=-0.05):
    rng = np.random.default_rng(seed)
    steps = rng.normal(loc=drift, scale=1.2, size=n)
    close = start_price + np.cumsum(steps)
    high = close + rng.uniform(0.2, 1.5, size=n)
    low = close - rng.uniform(0.2, 1.5, size=n)
    open_ = close - steps
    now = datetime.now(timezone.utc)
    dt = [now - timedelta(minutes=5 * (n - i)) for i in range(n)]
    return pd.DataFrame({"datetime": dt, "open": open_, "high": high, "low": low, "close": close})


if __name__ == "__main__":
    for seed, drift, label in [(7, -0.05, "mild downtrend"), (3, 0.05, "mild uptrend"), (1, 0.0, "choppy")]:
        df = synthetic_candles(seed=seed, drift=drift)
        sig = analyze(df, "5min")
        print(f"\n=== Scenario: {label} ===")
        if sig is None:
            print("No qualifying setup (expected sometimes — the bot skips rather than forcing a call).")
        else:
            print(format_signal(sig))
            lots = calculate_lot_size(1000, 1.0, abs(sig.entry - sig.stop_loss))
            print(f"\n📦 Suggested size: {lots} lots for $1000 balance @ 1% risk")
