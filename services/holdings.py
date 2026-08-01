from __future__ import annotations

import json
import re
from datetime import date
from io import BytesIO, StringIO
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
        match = re.search(r"(-?[0-9][0-9,]*(?:\.[0-9]+)?)%?\s*$", str(value))
        return float(match.group(1).replace(",", "")) if match else None
    except (TypeError, ValueError):
        return None


def _find_column(columns: list[str], words: tuple[str, ...]) -> str | None:
    for column in columns:
        normalized = str(column).lower().replace(" ", "")
        if any(word in normalized for word in words):
            return str(column)
    return None


def _clean_cell(value: object, label: str) -> str:
    return re.sub(rf"^\s*{re.escape(label)}\s+", "", str(value)).strip()


def _finalize(frame: pd.DataFrame) -> pd.DataFrame:
    for column in ("ticker", "company_name", "cusip", "isin"):
        if column not in frame:
            frame[column] = ""
        frame[column] = frame[column].fillna("").astype(str).str.strip()
    frame["weight_pct"] = pd.to_numeric(frame["weight_pct"], errors="coerce")
    frame = frame.dropna(subset=["weight_pct"])
    frame = frame[frame["company_name"].ne("")]
    return frame[["ticker", "company_name", "weight_pct", "cusip", "isin"]].sort_values("weight_pct", ascending=False).reset_index(drop=True)


def _fetch_ishares(ticker: str, official_source: str) -> tuple[pd.DataFrame, dict]:
    product = re.search(r"/products/(\d+)/", official_source)
    if not product:
        raise ValueError("The iShares official URL does not contain a product id.")
    endpoint = "https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v2/get-product-data"
    params = {
        "appSubType": "ISHARES", "appType": "PRODUCT_PAGE", "component": "holdings.all",
        "locale": "en_US", "portfolioId": product.group(1), "targetSite": "us-ishares",
        "userType": "individual", "excludeContent": "true", "asOfDate": "", "includeConfig": "true",
    }
    response = requests.get(endpoint, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    container = response.json()["componentsByNameMap"]["holdings"]["containersByNameMap"]["all"]
    points = container["dataPointsByNameMap"]

    def values(name: str) -> list:
        point = points.get(name, {})
        value = point.get("value", [])
        return value if isinstance(value, list) else []

    names = values("issueName")
    count = len(names)
    column = lambda name: (values(name) + [""] * count)[:count]
    frame = _finalize(pd.DataFrame({
        "ticker": column("ticker"), "company_name": names,
        "weight_pct": column("holdingPercent"), "cusip": column("cusip"), "isin": column("isin"),
    }))
    as_of = points.get("asOfDate", {}).get("formattedValue") or points.get("asOfDate", {}).get("value") or ""
    return frame, {"as_of": str(as_of), "retrieved_on": str(date.today()), "data_endpoint": response.url, "provider": "BlackRock/iShares official product-data API"}


def _fetch_ssga(ticker: str, official_source: str) -> tuple[pd.DataFrame, dict]:
    endpoint = f"https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{ticker.lower()}.xlsx"
    response = requests.get(endpoint, headers=HEADERS, timeout=30)
    response.raise_for_status()
    raw = pd.read_excel(BytesIO(response.content), header=None)
    as_of = str(raw.iloc[2, 1]).replace("As of ", "") if len(raw) > 3 else ""
    header_index = next((i for i, row in raw.iterrows() if str(row.iloc[0]).strip() == "Name" and str(row.iloc[1]).strip() == "Ticker"), None)
    if header_index is None:
        raise ValueError("The State Street official workbook format was not recognized.")
    table = raw.iloc[header_index + 1:].copy()
    table.columns = raw.iloc[header_index]
    frame = _finalize(pd.DataFrame({
        "ticker": table["Ticker"], "company_name": table["Name"], "weight_pct": table["Weight"],
        "cusip": table["Identifier"], "isin": "",
    }))
    return frame, {"as_of": as_of, "retrieved_on": str(date.today()), "data_endpoint": endpoint, "provider": "State Street official daily holdings workbook"}


def _fetch_first_trust(ticker: str, official_source: str) -> tuple[pd.DataFrame, dict]:
    endpoint = f"https://www.ftportfolios.com/Retail/Etf/EtfHoldings.aspx?Ticker={ticker}"
    response = requests.get(endpoint, headers=HEADERS, timeout=30)
    response.raise_for_status()
    for raw in pd.read_html(StringIO(response.text), header=None):
        if raw.shape[1] < 7 or str(raw.iloc[0, 0]).strip() != "Security Name":
            continue
        table = raw.iloc[1:].copy()
        table.columns = raw.iloc[0]
        frame = _finalize(pd.DataFrame({
            "ticker": table["Identifier"], "company_name": table["Security Name"],
            "weight_pct": table["Weighting"].map(_weight), "cusip": table["CUSIP"], "isin": "",
        }))
        match = re.search(r"Holdings of the Fund as of\s+([^<]+)", response.text, re.I)
        return frame, {"as_of": match.group(1).strip() if match else "", "retrieved_on": str(date.today()), "data_endpoint": endpoint, "provider": "First Trust official holdings page"}
    raise ValueError("The First Trust official full holdings table was not found.")


def _fetch_official_page(ticker: str, official_source: str) -> tuple[pd.DataFrame, dict]:
    """Extract a full holdings table only from the configured official issuer page.

    Issuers use different table labels, so the parser deliberately identifies the
    holding/name/weight columns rather than depending on one provider's markup.
    """
    host = official_source.lower()
    if "ishares.com" in host:
        return _fetch_ishares(ticker, official_source)
    if "ssga.com" in host:
        return _fetch_ssga(ticker, official_source)
    if "ftportfolios.com" in host:
        return _fetch_first_trust(ticker, official_source)
    response = requests.get(official_source, headers=HEADERS, timeout=30)
    response.raise_for_status()
    candidates = pd.read_html(StringIO(response.text))
    for table in candidates:
        table.columns = [str(column) for column in table.columns]
        columns = table.columns.tolist()
        ticker_col = _find_column(columns, ("ticker", "symbol"))
        name_col = _find_column(columns, ("holding", "company", "security", "name", "issuer"))
        weight_col = _find_column(columns, ("weight", "%", "allocation", "portfolio", "netassets"))
        cusip_col = _find_column(columns, ("cusip",))
        isin_col = _find_column(columns, ("isin",))
        if not name_col or not weight_col:
            continue
        frame = pd.DataFrame({
            "ticker": table[ticker_col].map(lambda value: _clean_cell(value, ticker_col)) if ticker_col else "",
            "company_name": table[name_col].map(lambda value: _clean_cell(value, name_col)),
            "weight_pct": table[weight_col].map(_weight),
            "cusip": table[cusip_col].map(lambda value: _clean_cell(value, cusip_col)) if cusip_col else "",
            "isin": table[isin_col].map(lambda value: _clean_cell(value, isin_col)) if isin_col else "",
        })
        frame = frame.dropna(subset=["weight_pct"])
        if len(frame) >= 2:
            return _finalize(frame), {
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
