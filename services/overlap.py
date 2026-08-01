from __future__ import annotations

import re
import pandas as pd


def _key(row: pd.Series) -> str | None:
    for column, prefix in (("cusip", "CUSIP"), ("isin", "ISIN"), ("ticker", "TICKER")):
        value = str(row.get(column, "")).strip().upper()
        if value and value not in {"NAN", "NONE"}:
            return f"{prefix}:{re.sub(r'[^A-Z0-9.-]', '', value)}"
    return None


def overlap_report(holdings: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    keyed: dict[str, dict[str, pd.Series]] = {}
    for etf, frame in holdings.items():
        keyed[etf] = {key: row for _, row in frame.iterrows() if (key := _key(row))}
    etfs = list(keyed)
    if not etfs:
        return pd.DataFrame(), pd.DataFrame()
    common = set.intersection(*(set(values) for values in keyed.values())) if len(keyed) >= 2 else set()
    rows = []
    for key in sorted(common):
        first = next(keyed[etf][key] for etf in etfs)
        row = {"match_key": key, "ticker": first.get("ticker", ""), "company_name": first.get("company_name", "")}
        row.update({f"{etf}_weight_pct": keyed[etf][key].get("weight_pct", None) for etf in etfs})
        rows.append(row)
    matrix = pd.DataFrame([[len(set(keyed[a]) & set(keyed[b])) for b in etfs] for a in etfs], index=etfs, columns=etfs)
    return pd.DataFrame(rows), matrix
