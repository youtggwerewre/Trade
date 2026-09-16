"""
Turns every posted signal into a tracked bet: logs it, walks forward through
later candles to see whether TP or SL was actually hit, and keeps a running
win/loss record. This is what lets the bot show a real track record instead
of just claiming confidence.
"""
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

LOG_FILE = Path(__file__).parent / "signals_log.json"
MAX_RECORDS_KEPT = 500


def load_records() -> list:
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return []


def _save(records: list):
    LOG_FILE.write_text(json.dumps(records[-MAX_RECORDS_KEPT:], indent=2))


def log_signal(sig, horizon_label: str = None):
    records = load_records()
    records.append({
        "id": (records[-1]["id"] + 1) if records else 1,
        "timeframe": sig.timeframe,
        "horizon_label": horizon_label,
        "direction": sig.direction,
        "entry": sig.entry,
        "sl": sig.stop_loss,
        "tp1": sig.tp1,
        "tp2": sig.tp2,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "tp1_hit": False,
        "status": "OPEN",   # OPEN -> TP2 | TP1_PARTIAL | SL
        "closed_at": None,
    })
    _save(records)


def update_outcomes(candles_by_timeframe: dict) -> list:
    """
    Walk every OPEN record forward through any candles that arrived after it
    opened. candles_by_timeframe: {timeframe: DataFrame} of recently fetched
    candles (datetime, open, high, low, close), reused from a normal scan —
    no extra API calls needed for timeframes already being scanned.

    Returns the list of records that closed (transitioned out of OPEN)
    during this call, so the caller can announce them.
    """
    records = load_records()
    just_closed = []

    for rec in records:
        if rec["status"] != "OPEN":
            continue
        df = candles_by_timeframe.get(rec["timeframe"])
        if df is None or df.empty:
            continue

        opened_at = pd.to_datetime(rec["opened_at"])
        if df["datetime"].dt.tz is None:
            opened_at = opened_at.tz_localize(None)
        new_candles = df[df["datetime"] > opened_at]
        if new_candles.empty:
            continue

        direction = rec["direction"]
        for _, c in new_candles.iterrows():
            if direction == "BUY":
                if not rec["tp1_hit"] and c["high"] >= rec["tp1"]:
                    rec["tp1_hit"] = True
                if c["high"] >= rec["tp2"]:
                    rec["status"] = "TP2"
                    break
                if c["low"] <= rec["sl"]:
                    rec["status"] = "TP1_PARTIAL" if rec["tp1_hit"] else "SL"
                    break
            else:  # SELL
                if not rec["tp1_hit"] and c["low"] <= rec["tp1"]:
                    rec["tp1_hit"] = True
                if c["low"] <= rec["tp2"]:
                    rec["status"] = "TP2"
                    break
                if c["high"] >= rec["sl"]:
                    rec["status"] = "TP1_PARTIAL" if rec["tp1_hit"] else "SL"
                    break

        if rec["status"] != "OPEN":
            rec["closed_at"] = datetime.now(timezone.utc).isoformat()
            just_closed.append(rec)

    if just_closed:
        _save(records)
    return just_closed


def losing_streak(records: list, n: int) -> bool:
    closed = [r for r in records if r["status"] != "OPEN"]
    if len(closed) < n:
        return False
    return all(r["status"] == "SL" for r in closed[-n:])


def stats_oneline(last_n: int = 50) -> str:
    records = load_records()[-last_n:]
    closed = [r for r in records if r["status"] != "OPEN"]
    open_count = sum(1 for r in records if r["status"] == "OPEN")
    if not closed:
        return "📈 Track record: building up — no closed signals yet"
    wins = sum(1 for r in closed if r["status"] in ("TP2", "TP1_PARTIAL"))
    losses = len(closed) - wins
    win_rate = 100 * wins / len(closed)
    return f"📈 Track record: {wins}W/{losses}L ({win_rate:.0f}%) · {open_count} open"


def stats_summary(last_n: int = 50) -> str:
    records = load_records()[-last_n:]
    closed = [r for r in records if r["status"] != "OPEN"]
    open_count = sum(1 for r in records if r["status"] == "OPEN")
    if not closed:
        return "📊 *Track record*\nNo closed signals yet — this builds up as signals play out."
    wins = sum(1 for r in closed if r["status"] in ("TP2", "TP1_PARTIAL"))
    losses = sum(1 for r in closed if r["status"] == "SL")
    win_rate = 100 * wins / len(closed)
    return (
        f"📊 *Track record* (last {len(closed)} closed)\n"
        f"Wins: {wins} · Losses: {losses} · Win rate: {win_rate:.0f}%\n"
        f"Currently open: {open_count}"
    )
