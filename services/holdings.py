from __future__ import annotations

import json
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "cache" / "holdings"
HEADERS = {"Accept": "application/json, text/plain, */*", "User-Agent": "Mozilla/5.0 sector-etf-dashboard/1.0"}


def _paths(ticker: str) -> tuple[Path, Path]:
    return CACHE_DIR / f"{ticker}.csv", CACHE_DIR / f"{ticker}.json"


def _pick(row: dict, *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _weight(value: str) -> float | None:
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _find_column(columns: list[str], words: tuple[str, ...]) -> str | None:
    for column in columns:
        normalized = str(column).lower().replace(" ", "")
        if any(word in normalized for word in words):
            return str(column)
    return None


def _fetch_official_page(ticker: str, official_source: str) -> tuple[pd.DataFrame, dict]:
    """Extract a full holdings table only from the configured official issuer page.

    Issuers use different table labels, so the parser deliberately identifies the
    holding/name/weight columns rather than depending on one provider's markup.
    """
    response = requests.get(official_source, headers=HEADERS, timeout=30)
    response.raise_for_status()
    candidates = pd.read_html(StringIO(response.text))
    for table in candidates:
        table.columns = [str(column) for column in table.columns]
        columns = table.columns.tolist()
        ticker_col = _find_column(columns, ("ticker", "symbol"))
        name_col = _find_column(columns, ("holding", "company", "security", "name", "issuer"))
        weight_col = _find_column(columns, ("weight", "%", "allocation", "portfolio"))
        if not name_col or not weight_col:
            continue
        frame = pd.DataFrame({
            "ticker": table[ticker_col].astype(str) if ticker_col else "",
            "company_name": table[name_col].astype(str),
            "weight_pct": table[weight_col].map(_weight),
        })
        frame = frame.dropna(subset=["weight_pct"])
        if len(frame) >= 2:
            return frame.sort_values("weight_pct", ascending=False), {
                "as_of": str(date.today()),
                "retrieved_on": str(date.today()),
                "data_endpoint": official_source,
                "provider": "Official ETF issuer page",
            }
    raise ValueError("The official issuer page did not expose a readable complete holdings table.")


def _read_cache(ticker: str) -> tuple[pd.DataFrame, dict] | None:
    csv_path, meta_path = _paths(ticker)
    if not csv_path.exists() or not meta_path.exists():
        return None
    return pd.read_csv(csv_path), json.loads(meta_path.read_text(encoding="utf-8"))


def get_holdings(ticker: str, official_source: str, refresh: bool = False) -> tuple[pd.DataFrame, dict, bool]:
    """Return full holdings. Remote failures are intentionally served from known cache only."""
    try:
        frame, meta = _fetch_official_page(ticker, official_source)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        csv_path, meta_path = _paths(ticker)
        frame.to_csv(csv_path, index=False)
        meta["official_source"] = official_source
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return frame, meta, False
    except Exception as exc:
        cached = _read_cache(ticker)
        if cached:
            frame, meta = cached
            meta["warning"] = f"Refresh failed; displaying last successful local cache. ({exc})"
            return frame, meta, True
        raise RuntimeError(f"Official holdings refresh failed: {exc}") from exc
