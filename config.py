import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
SIGNAL_BOT_TOKEN = os.getenv("SIGNAL_BOT_TOKEN", "")
NEWS_BOT_TOKEN = os.getenv("NEWS_BOT_TOKEN", "")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "")  # e.g. -1001234567890

# --- Market data (TwelveData: https://twelvedata.com, free tier works) ---
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")
SYMBOL = "XAU/USD"

# --- Signal engine defaults ---
DEFAULT_TIMEFRAMES = ["5min", "15min", "1h"]   # timeframes auto-scanned on start
MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 60
DEFAULT_INTERVAL_MINUTES = 5

RISK_REWARD_TP1 = 2.0
RISK_REWARD_TP2 = 3.0
ATR_SL_BUFFER = 0.5      # extra ATR fraction placed beyond swing high/low for the stop
SWING_LOOKBACK = 50       # candles used to find recent support/resistance
SIGNAL_COOLDOWN_MINUTES = 45  # don't re-post the same direction on the same timeframe within this window

# --- Position sizing ---
# ⚠️ Contract size varies by broker for XAUUSD (100oz/lot is common but not universal).
# Confirm yours in your broker's contract specification before trusting this number.
CONTRACT_SIZE_PER_LOT = 100
DEFAULT_RISK_PERCENT = 1.0
LOT_STEP = 0.01

# --- Hold-time label shown per timeframe (heuristic, not a guarantee) ---
HOLD_TIME_MAP = {
    "1min":  "5-15 min",
    "5min":  "15-60 min",
    "15min": "1-3 hours",
    "30min": "2-6 hours",
    "1h":    "4-12 hours",
    "4h":    "12-48 hours",
}

DISCLAIMER = (
    "⚠️ Automated technical analysis — not financial advice. "
    "Never risk more than you can afford to lose."
)

# --- Track record / circuit breaker ---
CIRCUIT_BREAKER_LOSSES = 3        # consecutive stop-outs that trigger a pause
CIRCUIT_BREAKER_COOLDOWN_HOURS = 2

# --- On-demand horizon picker (/signal command) ---
# (callback_key, display label, underlying candle timeframe used for the analysis)
HORIZON_OPTIONS = [
    ("next15", "⚡ Next 15 min", "5min"),
    ("next1h", "🕐 Next 1 hour", "15min"),
    ("next4h", "📈 Next 4 hours", "1h"),
]

# --- News bot ---
NEWS_DEFAULT_INTERVAL_MINUTES = 30
NEWS_MIN_INTERVAL_MINUTES = 15
NEWS_MAX_INTERVAL_MINUTES = 180
