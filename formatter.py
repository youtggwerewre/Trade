from signal_engine import Signal, session_note
import config

TF_LABELS = {
    "1min": "M1", "5min": "M5", "15min": "M15",
    "30min": "M30", "1h": "H1", "4h": "H4",
}


def format_signal(sig: Signal, track_record_line: str = "", horizon_label: str = None) -> str:
    tf = TF_LABELS.get(sig.timeframe, sig.timeframe)
    emoji = "🟢" if sig.direction == "BUY" else "🔴"
    header_tf = horizon_label if horizon_label else f"{tf} ({sig.hold_time})"

    lines = [
        "🏆 *XAUUSD PREMIUM SIGNAL*",
        f"Scanner confluence: {sig.score}/4 factors aligned · {sig.confidence} confidence",
        "──────────────────",
        "```",
        f"Signal: {sig.direction}",
        f"Entry: {sig.entry}",
        f"Stop Loss: {sig.stop_loss}",
        f"Take Profit 1: {sig.tp1}",
        f"Take Profit 2: {sig.tp2}",
        f"Confidence: {sig.confidence}",
        f"Risk:Reward: 1:{sig.rr}",
        f"Timeframe: {header_tf}",
        "```",
        "──────────────────",
        f"📍 Entry `{sig.entry}`",
        f"🛑 Stop `{sig.stop_loss}`",
        f"🎯 TP1 `{sig.tp1}`",
        f"🎯 TP2 `{sig.tp2}`",
        f"🛡️ R:R `1:{sig.rr}` · ⏳ Hold {header_tf}",
        "──────────────────",
        f"{emoji} ⏰ Entry trigger · {sig.direction} on retest of `{sig.entry}` "
        f"(zone `{sig.zone_low}–{sig.zone_high}`)",
        f"Valid for next ~15 min · {session_note()}",
        "If price moves through the zone without filling — setup expired, don't chase.",
        "──────────────────",
    ]
    if track_record_line:
        lines.append(track_record_line)
    lines.append(config.DISCLAIMER)
    return "\n".join(lines)


def format_outcome_message(rec: dict) -> str:
    tf = TF_LABELS.get(rec["timeframe"], rec["timeframe"])
    tag = rec.get("horizon_label") or tf

    if rec["status"] == "TP2":
        return (
            f"✅ *TP2 hit* — {rec['direction']} signal ({tag}) from entry `{rec['entry']}` "
            f"reached target 2 at `{rec['tp2']}`. Full target."
        )
    if rec["status"] == "TP1_PARTIAL":
        return (
            f"🟡 *Closed after TP1* — {rec['direction']} signal ({tag}) from entry `{rec['entry']}` "
            f"reached TP1 (`{rec['tp1']}`) before pulling back to stop. Partial win."
        )
    if rec["status"] == "SL":
        return (
            f"❌ *Stopped out* — {rec['direction']} signal ({tag}) from entry `{rec['entry']}` "
            f"hit stop at `{rec['sl']}`."
        )
    return ""
