import hashlib
import json
import logging
from pathlib import Path

import feedparser
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("news_bot")

STATE_FILE = Path(__file__).parent / "news_state.json"   # separate from signal_bot's state.json
SEEN_FILE = Path(__file__).parent / "seen_news.json"

# Public RSS feeds commonly used for gold/forex news.
# ⚠️ Verify these still resolve before relying on them long-term — providers
# sometimes change feed URLs without notice. Swap/add feeds here freely.
FEEDS = [
    "https://www.investing.com/rss/commodities_Gold.rss",
    "https://www.investing.com/rss/news_285.rss",   # Forex news
    "https://www.kitco.com/rss/KitcoNews.xml",
    "https://www.fxstreet.com/rss/news",
]

KEYWORDS = [
    "gold", "xau", "fed", "fomc", "interest rate", "inflation", "cpi",
    "dollar index", "dxy", "powell", "rate cut", "rate hike", "treasury yield",
    "non-farm", "nonfarm", "jobs report",
]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"interval_minutes": config.NEWS_DEFAULT_INTERVAL_MINUTES}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


state = load_state()


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    trimmed = list(seen)[-2000:]  # bound memory — dedup only needs recent items
    SEEN_FILE.write_text(json.dumps(trimmed))


def is_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(k in text for k in KEYWORDS)


async def check_news(context: ContextTypes.DEFAULT_TYPE):
    if not config.GROUP_CHAT_ID:
        log.warning("GROUP_CHAT_ID not set — skipping news check.")
        return

    seen = load_seen()
    new_items = []

    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            log.warning(f"Failed to parse {url}: {e}")
            continue

        for entry in feed.entries[:20]:
            link = entry.get("link", "")
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            if not link or not title:
                continue
            uid = hashlib.sha1(link.encode()).hexdigest()
            if uid in seen or not is_relevant(title, summary):
                continue
            new_items.append((uid, title, link))

    for uid, title, link in new_items:
        text = f"📰 *Gold/Forex News*\n{title}\n{link}"
        await context.bot.send_message(
            chat_id=config.GROUP_CHAT_ID, text=text,
            parse_mode="Markdown", disable_web_page_preview=False,
        )
        seen.add(uid)

    if new_items:
        save_seen(seen)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📰 Gold/Forex News Bot online.\n\n"
        "/interval <15-180> – how often it checks for news, in minutes\n"
        "/status – show current settings\n"
        "/check – run a check right now"
    )


async def interval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"Current interval: {state['interval_minutes']} min")
        return
    try:
        val = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /interval 30")
        return
    val = max(config.NEWS_MIN_INTERVAL_MINUTES, min(config.NEWS_MAX_INTERVAL_MINUTES, val))
    state["interval_minutes"] = val
    save_state(state)

    for job in context.job_queue.get_jobs_by_name("news_check"):
        job.schedule_removal()
    context.job_queue.run_repeating(check_news, interval=val * 60, first=5, name="news_check")

    await update.message.reply_text(f"News check interval set to {val} minutes.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Interval: {state['interval_minutes']} min\n"
        f"Feeds tracked: {len(FEEDS)}"
    )


async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Checking now…")
    await check_news(context)


def main():
    if not config.NEWS_BOT_TOKEN:
        raise SystemExit("Set NEWS_BOT_TOKEN in your .env")

    app = Application.builder().token(config.NEWS_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("interval", interval_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("check", check_cmd))

    app.job_queue.run_repeating(
        check_news, interval=state["interval_minutes"] * 60, first=10, name="news_check"
    )

    log.info("News bot starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
