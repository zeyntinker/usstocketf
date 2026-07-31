from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
CACHE_FILE = ROOT / "cache" / "prices.csv"


def _read_cache() -> pd.DataFrame:
    if not CACHE_FILE.exists():
        return pd.DataFrame()
    frame = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
    frame.index.name = "Date"
    return frame


def load_prices(tickers: list[str], refresh: bool = False) -> tuple[pd.DataFrame, str]:
    """Return adjusted daily closes, preferring a fresh download and then cache."""
    cached = _read_cache()
    # Downloading on each app process gives current data; cached values remain a safe fallback.
    try:
        start = (datetime.now() - timedelta(days=450)).date().isoformat()
        raw = yf.download(tickers, start=start, auto_adjust=True, progress=False, threads=True)
        prices = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if isinstance(prices, pd.Series):
            prices = prices.to_frame(name=tickers[0])
        prices = prices.reindex(columns=tickers).dropna(how="all").sort_index()
        if not prices.empty:
            CACHE_FILE.parent.mkdir(exist_ok=True)
            prices.to_csv(CACHE_FILE, index_label="Date")
            return prices, "Yahoo Finance (fresh)"
    except Exception:
        pass
    if cached.empty:
        raise RuntimeError("Price download failed and no local price cache exists.")
    return cached.reindex(columns=tickers).dropna(how="all"), "Yahoo Finance (local cache)"
