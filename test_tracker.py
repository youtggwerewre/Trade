import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd

import tracker

LOG_FILE = Path(__file__).parent / "signals_log.json"


class FakeSig:
    def __init__(self, direction, entry, sl, tp1, tp2, timeframe="5min"):
        self.direction, self.entry, self.stop_loss = direction, entry, sl
        self.tp1, self.tp2, self.timeframe = tp1, tp2, timeframe


def candles_after(base_time, minutes_list, values):
    """values: list of (open,high,low,close) tuples"""
    rows = []
    for m, (o, h, l, c) in zip(minutes_list, values):
        rows.append({"datetime": base_time + timedelta(minutes=m), "open": o, "high": h, "low": l, "close": c})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # start clean
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Scenario 1: BUY that runs straight to TP2 (full win)
    tracker.log_signal(FakeSig("BUY", 4180, 4170, 4190, 4200))
    time_opened = pd.to_datetime(tracker.load_records()[0]["opened_at"])

    df1 = candles_after(now, [5, 10, 15], [
        (4181, 4192, 4180, 4191),   # touches tp1 (4190)
        (4191, 4201, 4190, 4200),   # touches tp2 (4200) -> should close TP2
        (4200, 4205, 4198, 4202),  # irrelevant, already closed
    ])

    # Scenario 2: SELL that gets stopped out directly
    tracker.log_signal(FakeSig("SELL", 4180, 4190, 4170, 4160))
    df2 = candles_after(now, [5, 10], [
        (4181, 4192, 4179, 4191),  # high 4192 >= sl 4190 -> SL immediately
        (4191, 4195, 4185, 4193),
    ])

    # Scenario 3: BUY that hits TP1 then reverses to SL -> should be TP1_PARTIAL not SL
    tracker.log_signal(FakeSig("BUY", 4180, 4170, 4190, 4210))
    df3 = candles_after(now, [5, 10], [
        (4181, 4192, 4180, 4191),  # touches tp1
        (4191, 4193, 4168, 4170),  # then drops through sl 4170
    ])

    candles_by_tf = {"5min": pd.concat([df1, df2, df3]).reset_index(drop=True)}
    closed = tracker.update_outcomes(candles_by_tf)

    print(f"Closed this pass: {len(closed)}")
    for r in tracker.load_records():
        print(f"  #{r['id']} {r['direction']} -> {r['status']} (tp1_hit={r['tp1_hit']})")

    print()
    print(tracker.stats_summary())
    print(tracker.stats_oneline())

    expected = {1: "TP2", 2: "SL", 3: "TP1_PARTIAL"}
    ok = all(r["status"] == expected[r["id"]] for r in tracker.load_records())
    print("\n" + ("✅ ALL SCENARIOS CORRECT" if ok else "❌ MISMATCH — check logic"))
