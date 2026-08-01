import pandas as pd

from services.overlap import overlap_report


def test_overlap_prefers_cusip_and_reports_pair_counts():
    left = pd.DataFrame([
        {"ticker": "AAA", "company_name": "Alpha", "weight_pct": 5.0, "cusip": "123456789", "isin": ""},
        {"ticker": "BBB", "company_name": "Beta", "weight_pct": 3.0, "cusip": "987654321", "isin": ""},
    ])
    right = pd.DataFrame([
        {"ticker": "ALPHA", "company_name": "Alpha renamed", "weight_pct": 4.0, "cusip": "123456789", "isin": ""},
    ])
    common, matrix = overlap_report({"ETF1": left, "ETF2": right})
    assert common["match_key"].tolist() == ["CUSIP:123456789"]
    assert matrix.loc["ETF1", "ETF2"] == 1


def test_one_fund_is_not_described_as_an_intersection():
    frame = pd.DataFrame([{"ticker": "AAA", "company_name": "Alpha", "weight_pct": 5.0, "cusip": "", "isin": ""}])
    common, matrix = overlap_report({"ETF1": frame})
    assert common.empty
    assert matrix.loc["ETF1", "ETF1"] == 1
