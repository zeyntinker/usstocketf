import pandas as pd

from services.ranking import ranked_frame, resolve_dates, returns_between


def test_return_and_full_rank_order():
    dates = pd.bdate_range("2026-01-02", periods=4)
    prices = pd.DataFrame({"AAA": [100, 105, 110, 120], "BBB": [100, 98, 97, 95]}, index=dates)
    universe = pd.DataFrame({"sector": ["A", "B"], "ticker": ["AAA", "BBB"], "etf_name": ["A fund", "B fund"], "official_source": ["a", "b"]})
    result = ranked_frame(universe, returns_between(prices, dates[0], dates[-1]))
    assert result["ticker"].tolist() == ["AAA", "BBB"]
    assert result["rank"].tolist() == [1, 2]
    assert round(result.iloc[0]["return_pct"], 8) == 20


def test_date_resolution_uses_next_start_and_previous_end():
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    prices = pd.DataFrame({"AAA": [1, 2, 3]}, index=dates)
    start, end = resolve_dates(prices, pd.Timestamp("2026-01-03"), pd.Timestamp("2026-01-05"))
    assert start == pd.Timestamp("2026-01-05")
    assert end == pd.Timestamp("2026-01-05")
