from __future__ import annotations

import pandas as pd
import yfinance as yf


SEARCH_ALIASES = {
    "Airlines": ["airline", "transportation ETF", "travel ETF"],
}

# Verified issuer product pages. This list supplies an official source only; it
# never supplies or guesses holdings data.
OFFICIAL_SOURCES = {
    "IYT": "https://www.ishares.com/us/products/239501/ishares-transportation-average-etf",
    "FTXR": "https://www.ftportfolios.com/Retail/Etf/EtfHoldings.aspx?Ticker=FTXR",
    "XTN": "https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-transportation-etf-xtn",
    "FDRV": "https://fundresearch.fidelity.com/mutual-funds/summary/316092220",
}


def verified_official_source(ticker: str) -> str:
    return OFFICIAL_SOURCES.get(ticker.upper(), "")


def search_sector_etfs(sector: str) -> pd.DataFrame:
    """Use Yahoo Finance only to discover ETF candidates, never holdings."""
    rows = []
    queries = [f"{sector} ETF", sector, *SEARCH_ALIASES.get(sector, [])]
    for query in dict.fromkeys(queries):
        result = yf.Search(query, max_results=30, news_count=0)
        for quote in result.quotes:
            if str(quote.get("quoteType", "")).upper() != "ETF":
                continue
            symbol = quote.get("symbol")
            exchange = str(quote.get("exchange") or "")
            if symbol and not symbol.endswith(".MX") and exchange not in {"KSC", "SHH", "SHZ"}:
                rows.append({"ticker": symbol.upper(), "etf_name": quote.get("longname") or quote.get("shortname") or symbol, "exchange": exchange})
    return pd.DataFrame(rows, columns=["ticker", "etf_name", "exchange"]).drop_duplicates("ticker")
