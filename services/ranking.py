from __future__ import annotations

import pandas as pd

LOOKBACKS = {
    "1D (1 trading day)": 1,
    "1W (5 trading days)": 5,
    "2W (10 trading days)": 10,
    "1M (21 trading days)": 21,
    "2M (42 trading days)": 42,
    "3M (63 trading days)": 63,
    "6M (126 trading days)": 126,
}

# The lecture-derived leadership score intentionally stays focused on the
# established monthly horizons, even though shorter ranking views are available.
COMPOSITE_LOOKBACKS = {label: days for label, days in LOOKBACKS.items() if days in (21, 42, 63, 126)}


def resolve_dates(prices: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    available = prices.dropna(how="all").index
    starts = available[available >= pd.Timestamp(start)]
    ends = available[available <= pd.Timestamp(end)]
    if starts.empty or ends.empty or starts[0] > ends[-1]:
        raise ValueError("The selected dates contain no usable trading-day prices.")
    return starts[0], ends[-1]


def returns_between(prices: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    resolved_start, resolved_end = resolve_dates(prices, start, end)
    first = prices.loc[resolved_start]
    last = prices.loc[resolved_end]
    return ((last / first - 1) * 100).dropna()


def returns_lookback(prices: pd.DataFrame, days: int) -> pd.Series:
    clean = prices.dropna(how="all")
    if len(clean) <= days:
        raise ValueError("Not enough price history for this lookback.")
    return ((clean.iloc[-1] / clean.iloc[-days - 1] - 1) * 100).dropna()


def ranked_frame(universe: pd.DataFrame, returns: pd.Series) -> pd.DataFrame:
    frame = universe.copy()
    frame["return_pct"] = frame["ticker"].map(returns)
    frame = frame.dropna(subset=["return_pct"]).sort_values("return_pct", ascending=False).reset_index(drop=True)
    frame.insert(0, "rank", frame.index + 1)
    return frame


def composite_ranking(universe: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    ranks: dict[str, pd.Series] = {}
    for label, days in LOOKBACKS.items():
        ranks[label] = returns_lookback(prices, days).rank(ascending=False, method="min")
    all_ranks = pd.DataFrame(ranks)

    composite_ranks: dict[str, pd.Series] = {}
    for label, days in COMPOSITE_LOOKBACKS.items():
        composite_ranks[label] = all_ranks[label]
    combined = pd.DataFrame(composite_ranks)
    score = combined.mean(axis=1)

    path_labels = list(reversed(list(LOOKBACKS)))
    rank_path = all_ranks.apply(
        lambda row: " → ".join(f"{label.split()[0]} #{int(row[label])}" for label in path_labels if pd.notna(row[label])),
        axis=1,
    )
    frame = universe.copy()
    frame["average_rank"] = frame["ticker"].map(score)
    frame["rank_movement"] = frame["ticker"].map(rank_path)
    return frame.dropna(subset=["average_rank"]).sort_values("average_rank").reset_index(drop=True)
