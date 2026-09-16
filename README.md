# XAUUSD Signal Suite

Two Telegram bots meant to sit in the same group:

1. **`signal_bot.py`** — scans real XAU/USD price data and posts a graded
   BUY/SELL setup (entry, SL, TP1/TP2, confidence, R:R, hold-time, lot size)
   whenever its indicators actually line up. It also **tracks every signal
   it posts** and reports back when TP or SL is actually hit, and **pauses
   itself** after a losing streak instead of forcing more calls.
2. **`news_bot.py`** — watches gold/forex RSS feeds every 30 min (adjustable)
   and drops relevant headlines (Fed, CPI, NFP, gold-specific news) into the
   group.

## How the signal engine actually works

No magic "AI prediction" — it's transparent multi-indicator confluence, the
same logic real technical-analysis desks use:

- **Trend** — EMA20/EMA50/EMA(long) stack direction
- **Momentum** — RSI(14) and MACD histogram
- **Structure** — price vs. recent swing high/low midpoint

Each of the 4 factors "votes" bullish or bearish. If they disagree evenly, no
signal is posted. Otherwise: 2/4 agreeing = **Low** confidence, 3/4 =
**Medium**, 4/4 = **High** — and every posted signal shows the exact
confluence score ("3/4 factors aligned"), not just a label. Stop-loss sits
beyond the nearest swing point plus an ATR buffer; TP1/TP2 are 2R/3R by
default (edit in `config.py`).

Every message ends with a one-line disclaimer — keep it. Anything posted
automatically into a group where people may trade real money on it should
say plainly that it's automated TA, not advice.

## Track record and circuit breaker

Every signal gets logged (`tracker.py`, stored in `signals_log.json`) and
checked against later candles to see whether TP1, TP2, or SL was hit first.
The bot posts that outcome back to the group (✅ TP2 hit / 🟡 partial / ❌
stopped out), and every new signal shows the running win rate so far
("📈 Track record: 12W/5L (71%) · 2 open") — proof instead of a claimed
confidence score.

If **3 signals in a row hit stop-loss**, the bot pauses new signals for 2
hours and says so in the group, while still tracking and reporting on any
signals still open. Both numbers are in `config.py`
(`CIRCUIT_BREAKER_LOSSES`, `CIRCUIT_BREAKER_COOLDOWN_HOURS`).

Use `/stats` any time for the full breakdown.

## On-demand horizon picker

`/signal` gives you a menu — **Next 15 min**, **Next 1 hour**, **Next 4
hours** — pick one and it scans the matching timeframe immediately and
replies with a graded setup (or tells you plainly there's no clear edge
right now). These on-demand reads get tracked too, same as auto-posted ones.

## Setup

1. **Create both bots** with [@BotFather](https://t.me/BotFather) → `/newbot`
   twice → save the two tokens.
2. **Add both bots to your group.** If it's a channel (broadcast-only), make
   them admins with "Post Messages" permission. A normal group usually just
   needs them added as members.
3. **Get your group's chat ID**: send any message in the group, then visit
   `https://api.telegram.org/bot<SIGNAL_BOT_TOKEN>/getUpdates` in a browser —
   look for `"chat":{"id": ...}` (it'll be a negative number, or start with
   `-100` for supergroups/channels).
4. **Get a free TwelveData API key** at twelvedata.com — covers XAU/USD
   intraday candles on the free tier.
5. Copy `.env.example` → `.env` and fill in all four values.
6. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
7. Try it offline first (no keys needed, sanity-checks the logic/format):
   ```
   python test_offline.py
   python test_tracker.py
   ```
8. Run both bots — one command starts both, restarts either one if it
   crashes, and Ctrl+C stops both cleanly:
   ```
   python run_all.py
   ```
   For real 24/7 uptime on a VPS, run that inside `tmux`, `screen`, or a
   process manager like `pm2`/`systemd` so it survives you disconnecting.
9. In the group:
   - `/signal` → on-demand read for next 15m / 1h / 4h
   - `/timeframes` → tap to toggle which of M1–H4 auto-scan in the background
   - `/interval 15` → background scan frequency (5–60 min, signal bot)
   - `/interval 30` → news check frequency (15–180 min, news bot)
   - `/setup 1000 1` → $1000 balance, 1% risk per trade, for lot sizing
   - `/contractsize 100` → match your broker's XAUUSD contract spec (see below)
   - `/stats` → track record so far
   - `/scan` → run the background scan immediately
   - `/status` → current settings on either bot

## Things to double-check before trusting this with real money

- **Lot sizing assumes 100 oz per standard lot** (`CONTRACT_SIZE_PER_LOT` in
  `config.py`, overridable per-bot with `/contractsize`). Confirm this
  against your actual broker's contract spec — it isn't universal.
- **Small accounts will often see a size warning instead of a lot number.**
  On a standard 100oz contract, even the smallest tradeable lot (0.01) risks
  ~$1 per $1 of stop distance — so a typical $5–15 gold stop already risks
  $5–15. On a $10–200 account that's a large chunk of the balance, and the
  bot will say so explicitly rather than quietly suggesting an oversized
  position. If your broker offers a smaller XAUUSD contract for micro/cent
  accounts, set it with `/contractsize` to get real numbers back.
- **RSS feed URLs** in `news_bot.py` are commonly-used public feeds, but
  sites change endpoints occasionally — verify they're still live and swap
  in others if not.
- **The track record only reflects what the bot has posted since you started
  running it** — it isn't a backtest, and a short run of good or bad luck
  won't mean much statistically. Let it accumulate before trusting the
  win rate.
- **This wasn't live-tested end-to-end** (the dev sandbox that built this
  has no access to the Telegram or TwelveData APIs) — the logic is verified
  via `test_offline.py` / `test_tracker.py`, but test the live path yourself
  once your API keys are in, and paper-trade for a while before sizing up.

## Design note

The track record and circuit-breaker features were prompted by looking at
[tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills),
a Claude-skills toolkit for traders. Worth knowing: that project explicitly
is *not* a signal service — its own README states it's built around human
decision gates, position sizing, and post-trade review rather than automated
calls. The pieces borrowed here are exactly that spirit — accountability
(did the signal actually work?) and a risk gate (stop after a losing streak)
— adapted into this bot's own code, not copied from theirs.

## Optional phase 2

If you want a natural-language "market read" line added under each signal
(e.g. "Gold is testing resistance near X after failing to hold the H1 50-EMA,
while RSI shows fading momentum…"), that's a good add-on using the Anthropic
API — but it should only *narrate* numbers the engine already computed, never
generate its own price levels. Happy to wire that in if you want it.
