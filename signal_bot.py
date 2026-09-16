import json
import logging
import time
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)

import config
import tracker
from data_feed import fetch_candles
from signal_engine import analyze
from formatter import format_signal, format_outcome_message
from lot_size import lot_size_breakdown

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("signal_bot")

STATE_FILE = Path(__file__).parent / "state.json"
ALL_TIMEFRAMES = ["1min", "5min", "15min", "30min", "1h", "4h"]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "active_timeframes": list(config.DEFAULT_TIMEFRAMES),
        "interval_minutes": config.DEFAULT_INTERVAL_MINUTES,
        "balance": 1000.0,
        "risk_percent": config.DEFAULT_RISK_PERCENT,
        "contract_size": config.CONTRACT_SIZE_PER_LOT,  # oz per lot — adjustable via /contractsize
        "last_signal": {},              # timeframe -> {"direction":..., "ts":...}
        "circuit_breaker_until": None,  # epoch seconds, or None
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


state = load_state()


# ---------------------------------------------------------------- keyboards

def build_timeframe_keyboard():
    rows = []
    for tf in ALL_TIMEFRAMES:
        mark = "✅" if tf in state["active_timeframes"] else "▫️"
        rows.append([InlineKeyboardButton(f"{mark} {tf}", callback_data=f"tf:{tf}")])
    rows.append([InlineKeyboardButton("Done", callback_data="tf:done")])
    return InlineKeyboardMarkup(rows)


def build_horizon_keyboard():
    rows = [[InlineKeyboardButton(label, callback_data=f"hz:{key}")]
            for key, label, _tf in config.HORIZON_OPTIONS]
    return InlineKeyboardMarkup(rows)


def build_size_line(sl_distance: float) -> str:
    b = lot_size_breakdown(state["balance"], state["risk_percent"], sl_distance, state.get("contract_size"))
    if b["affordable"]:
        return (
            f"📦 Size: `{b['lots']}` lots — risks ${b['risk_amount']} "
            f"({b['risk_percent_actual']}% of ${state['balance']})"
        )
    return (
        f"⚠️ *Too small to size safely* at ${state['balance']} balance / {state['risk_percent']}% risk "
        f"and a {round(sl_distance, 2)} stop — even the smallest tradeable size (`{config.LOT_STEP}` lot) "
        f"would risk ${b['risk_amount']} ({b['risk_percent_actual']}% of your account). "
        f"Options: use `/contractsize` if your broker offers smaller XAUUSD contracts, trade a smaller "
        f"instrument, or grow the account before sizing into gold at standard lots."
    )


# ------------------------------------------------------------------ commands

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 XAUUSD Signal Scanner online.\n\n"
        "/signal – pick a horizon (next 15m / 1h / 4h) for an on-demand read\n"
        "/timeframes – choose which timeframes auto-scan in the background\n"
        "/interval <5-60> – how often the background scanner checks, in minutes\n"
        "/setup <balance> <risk%> – lot-size inputs, e.g. /setup 1000 1\n"
        "/contractsize <oz> – match your broker's XAUUSD contract size (default 100)\n"
        "/stats – track record of past signals (win rate, open count)\n"
        "/status – show current settings\n"
        "/scan – run the background scan right now"
    )


async def timeframes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Select timeframes to auto-scan:", reply_markup=build_timeframe_keyboard())


async def timeframe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tf = query.data.split(":")[1]
    if tf == "done":
        await query.edit_message_text(f"Active timeframes: {', '.join(state['active_timeframes']) or 'none'}")
        return
    if tf in state["active_timeframes"]:
        state["active_timeframes"].remove(tf)
    else:
        state["active_timeframes"].append(tf)
    save_state(state)
    await query.edit_message_reply_markup(reply_markup=build_timeframe_keyboard())


async def interval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"Current interval: {state['interval_minutes']} min")
        return
    try:
        val = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /interval 15")
        return
    val = max(config.MIN_INTERVAL_MINUTES, min(config.MAX_INTERVAL_MINUTES, val))
    state["interval_minutes"] = val
    save_state(state)

    for job in context.job_queue.get_jobs_by_name("auto_scan"):
        job.schedule_removal()
    context.job_queue.run_repeating(auto_scan_job, interval=val * 60, first=5, name="auto_scan")

    await update.message.reply_text(f"Scan interval set to {val} minutes.")


async def setup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setup <balance_usd> <risk_percent>")
        return
    try:
        balance = float(context.args[0])
        risk_pct = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Usage: /setup 1000 1")
        return
    state["balance"] = balance
    state["risk_percent"] = risk_pct
    save_state(state)
    await update.message.reply_text(f"Saved: balance=${balance}, risk={risk_pct}% per trade.")


async def contractsize_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = state.get("contract_size", config.CONTRACT_SIZE_PER_LOT)
    if not context.args:
        await update.message.reply_text(
            f"Current contract size: {current} oz per lot (standard XAUUSD is usually 100).\n"
            "Usage: /contractsize <oz_per_lot> — check your broker's XAUUSD contract "
            "specification first; some offer smaller contracts on micro/cent accounts, "
            "which is what actually makes small balances tradeable."
        )
        return
    try:
        val = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /contractsize 100")
        return
    if val <= 0:
        await update.message.reply_text("Contract size must be a positive number.")
        return
    state["contract_size"] = val
    save_state(state)
    await update.message.reply_text(
        f"Contract size set to {val} oz/lot. Suggested sizes will now use this — "
        f"double check it matches what your broker actually quotes for XAUUSD."
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    paused = " (⏸️ paused)" if is_paused() else ""
    await update.message.reply_text(
        "Timeframes: " + ", ".join(state["active_timeframes"]) + "\n"
        f"Interval: {state['interval_minutes']} min{paused}\n"
        f"Balance: ${state['balance']} · Risk: {state['risk_percent']}% · "
        f"Contract: {state.get('contract_size', config.CONTRACT_SIZE_PER_LOT)} oz/lot\n\n"
        + tracker.stats_oneline()
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tracker.stats_summary(), parse_mode="Markdown")


# ------------------------------------------------------ on-demand /signal

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pick a horizon:", reply_markup=build_horizon_keyboard())


async def horizon_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[1]
    match = next((h for h in config.HORIZON_OPTIONS if h[0] == key), None)
    if not match:
        return
    _, label, tf = match
    await query.edit_message_text(f"Scanning for {label}…")

    try:
        df = fetch_candles(tf)
    except Exception as e:
        await query.edit_message_text(f"Couldn't fetch data: {e}")
        return

    sig = analyze(df, tf)
    if not sig:
        await query.edit_message_text(
            f"No clear setup for {label} right now — indicators are mixed. That's by design, not a bug."
        )
        return

    text = format_signal(sig, tracker.stats_oneline(), horizon_label=label) + (
        f"\n{build_size_line(abs(sig.entry - sig.stop_loss))}"
    )

    if is_paused():
        text = (
            "⚠️ Auto-signals are paused after a losing streak — here's the raw read anyway:\n\n"
        ) + text

    await query.edit_message_text(text, parse_mode="Markdown")
    tracker.log_signal(sig, horizon_label=label)


# --------------------------------------------------------- circuit breaker

def is_paused() -> bool:
    until = state.get("circuit_breaker_until")
    return bool(until and time.time() < until)


def maybe_trigger_circuit_breaker() -> bool:
    """Returns True the moment the breaker newly trips (so caller can announce it)."""
    if is_paused():
        return False
    if tracker.losing_streak(tracker.load_records(), config.CIRCUIT_BREAKER_LOSSES):
        state["circuit_breaker_until"] = time.time() + config.CIRCUIT_BREAKER_COOLDOWN_HOURS * 3600
        save_state(state)
        return True
    return False


def cooldown_ok(tf: str, direction: str) -> bool:
    last = state["last_signal"].get(tf)
    if not last:
        return True
    if last["direction"] != direction:
        return True
    age_min = (time.time() - last["ts"]) / 60
    return age_min >= config.SIGNAL_COOLDOWN_MINUTES


# --------------------------------------------------------------- main scan

async def run_scan(context: ContextTypes.DEFAULT_TYPE, chat_id):
    # 1. Fetch candles for every timeframe we need (active scan set + any
    #    timeframe with an open tracked signal, even if it's off the active list).
    fetched = {}
    for tf in state["active_timeframes"]:
        try:
            fetched[tf] = fetch_candles(tf)
        except Exception as e:
            log.warning(f"Fetch failed for {tf}: {e}")

    open_tfs = {r["timeframe"] for r in tracker.load_records() if r["status"] == "OPEN"}
    for tf in open_tfs - set(fetched):
        try:
            fetched[tf] = fetch_candles(tf)
        except Exception as e:
            log.warning(f"Fetch failed for {tf}: {e}")

    # 2. Update the track record using data we already have — no extra API calls.
    closed_now = tracker.update_outcomes(fetched)
    for rec in closed_now:
        await context.bot.send_message(
            chat_id=chat_id, text=format_outcome_message(rec), parse_mode="Markdown"
        )

    # 3. Circuit breaker check, using the freshest possible track record.
    if maybe_trigger_circuit_breaker():
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⏸️ {config.CIRCUIT_BREAKER_LOSSES} stop-outs in a row — pausing new signals for "
                f"{config.CIRCUIT_BREAKER_COOLDOWN_HOURS}h while conditions look unfavorable. "
                f"Open signals are still being tracked and will post their outcome."
            ),
        )

    if is_paused():
        return  # skip generating new signals while paused

    # 4. Look for new setups on the active timeframes.
    for tf in state["active_timeframes"]:
        df = fetched.get(tf)
        if df is None:
            continue
        sig = analyze(df, tf)
        if not sig or not cooldown_ok(tf, sig.direction):
            continue

        text = format_signal(sig, tracker.stats_oneline()) + (
            f"\n{build_size_line(abs(sig.entry - sig.stop_loss))}"
        )

        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        tracker.log_signal(sig)
        state["last_signal"][tf] = {"direction": sig.direction, "ts": time.time()}
        save_state(state)


async def auto_scan_job(context: ContextTypes.DEFAULT_TYPE):
    if not config.GROUP_CHAT_ID:
        log.warning("GROUP_CHAT_ID not set — skipping auto scan.")
        return
    await run_scan(context, config.GROUP_CHAT_ID)


async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Scanning now…")
    await run_scan(context, update.effective_chat.id)


def main():
    if not config.SIGNAL_BOT_TOKEN:
        raise SystemExit("Set SIGNAL_BOT_TOKEN in your .env")

    app = Application.builder().token(config.SIGNAL_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CallbackQueryHandler(horizon_callback, pattern=r"^hz:"))
    app.add_handler(CommandHandler("timeframes", timeframes_cmd))
    app.add_handler(CallbackQueryHandler(timeframe_callback, pattern=r"^tf:"))
    app.add_handler(CommandHandler("interval", interval_cmd))
    app.add_handler(CommandHandler("setup", setup_cmd))
    app.add_handler(CommandHandler("contractsize", contractsize_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))

    app.job_queue.run_repeating(
        auto_scan_job, interval=state["interval_minutes"] * 60, first=10, name="auto_scan"
    )

    log.info("Signal bot starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
