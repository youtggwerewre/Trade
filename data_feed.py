import requests
import pandas as pd

import config

BASE_URL = "https://api.twelvedata.com/time_series"


def fetch_candles(interval: str, outputsize: int = 300) -> pd.DataFrame:
    """
    Fetch OHLC candles for XAU/USD from TwelveData.
    interval: one of "1min","5min","15min","30min","1h","4h"
    Returns a DataFrame sorted oldest -> newest with columns:
    datetime, open, high, low, close
    """
    params = {
        "symbol": config.SYMBOL,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": config.TWELVEDATA_API_KEY,
        "format": "JSON",
    }
    resp = requests.get(BASE_URL, params=params, timeout=15)
    data = resp.json()

    if "values" not in data:
        raise RuntimeError(f"TwelveData error for {interval}: {data}")

    df = pd.DataFrame(data["values"])
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df
