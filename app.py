from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.holdings import get_holdings
from services.discovery import search_sector_etfs, verified_official_source
from services.overlap import overlap_report
from services.prices import load_prices
from services.ranking import LOOKBACKS, composite_ranking, ranked_frame, resolve_dates, returns_between, returns_lookback

ROOT = Path(__file__).resolve().parent
UNIVERSE_PATH = ROOT / "data" / "universe.csv"
SHUTDOWN_FLAG = ROOT / "cache" / "shutdown.flag"

st.set_page_config(page_title="Sector ETF Leadership", page_icon="📈", layout="wide")


@st.cache_data(ttl=900, show_spinner=False)
def cached_prices(tickers: tuple[str, ...]) -> tuple[pd.DataFrame, str]:
    return load_prices(list(tickers), refresh=True)


@st.cache_data(ttl=86_400, show_spinner=False)
def cached_holdings(ticker: str, source: str) -> tuple[pd.DataFrame, dict, bool]:
    return get_holdings(ticker, source, refresh=True)


def format_ranking(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame[["rank", "sector", "ticker", "etf_name", "return_pct"]].copy()
    display.columns = ["순위", "섹터", "ETF", "ETF 이름", "수익률"]
    display["수익률"] = display["수익률"].map(lambda value: f"{value:+.2f}%")
    return display


def normalized_chart(prices: pd.DataFrame, tickers: list[str], start: pd.Timestamp, end: pd.Timestamp) -> go.Figure:
    first, last = resolve_dates(prices, start, end)
    view = prices.loc[first:last, tickers].ffill().dropna(how="all")
    figure = go.Figure()
    for ticker in tickers:
        series = view[ticker].dropna()
        if not series.empty:
            normalized = (series / series.iloc[0] - 1) * 100
            figure.add_trace(go.Scatter(x=normalized.index, y=normalized, mode="lines", name=ticker, hovertemplate="%{x|%Y-%m-%d}<br>%{y:+.2f}%<extra>" + ticker + "</extra>"))
    figure.update_layout(
        height=490,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        font=dict(color="#e5e7eb"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(gridcolor="#263244", showspikes=True),
        yaxis=dict(title="정규화 수익률", ticksuffix="%", gridcolor="#263244", zerolinecolor="#64748b"),
        hovermode="x unified",
        dragmode="pan",
    )
    return figure


def request_shutdown() -> None:
    SHUTDOWN_FLAG.parent.mkdir(exist_ok=True)
    SHUTDOWN_FLAG.write_text("requested", encoding="utf-8")
    st.components.v1.html("<script>setTimeout(() => window.close(), 200);</script>", height=0)
    st.success("앱을 종료합니다.")


def main() -> None:
    universe = pd.read_csv(UNIVERSE_PATH)
    tickers = universe["ticker"].tolist()
    st.title("Sector ETF Leadership")
    st.caption("42개 고정 섹터 ETF의 상대 성과와 공식 holdings를 한곳에서 분석합니다.")

    with st.sidebar:
        st.header("분석 설정")
        if st.button("시세 새로고침", use_container_width=True):
            cached_prices.clear()
            cached_holdings.clear()
            st.rerun()
        if st.button("프로그램 종료", type="primary", use_container_width=True):
            request_shutdown()
            return

    try:
        with st.spinner("42개 ETF 시세를 불러오는 중입니다…"):
            prices, price_status = cached_prices(tuple(tickers))
    except RuntimeError as exc:
        st.error(str(exc))
        return

    available_start, available_end = prices.index.min(), prices.index.max()
    with st.sidebar:
        st.caption(f"시세: {price_status} · 마지막 거래일: {available_end:%Y-%m-%d}")
        mode = st.radio("순위 기준", ["1일", "1주", "2주", "1개월", "2개월", "3개월", "6개월", "사용자 지정"], index=0)
        if mode == "사용자 지정":
            start_date = st.date_input("시작일", value=(available_end - timedelta(days=90)).date(), min_value=available_start.date(), max_value=available_end.date())
            end_date = st.date_input("종료일", value=available_end.date(), min_value=available_start.date(), max_value=available_end.date())
        else:
            days = {"1일": 1, "1주": 5, "2주": 10, "1개월": 21, "2개월": 42, "3개월": 63, "6개월": 126}[mode]
            start_date = prices.index[-days - 1].date()
            end_date = available_end.date()

    try:
        resolved_start, resolved_end = resolve_dates(prices, pd.Timestamp(start_date), pd.Timestamp(end_date))
        selected_returns = returns_between(prices, resolved_start, resolved_end)
    except ValueError as exc:
        st.error(str(exc))
        return

    selected_rank = ranked_frame(universe, selected_returns)
    st.subheader(f"{mode} 순위 — 42개 ETF 전체")
    st.caption(f"적용 거래일: {resolved_start:%Y-%m-%d} → {resolved_end:%Y-%m-%d} · 조정종가 기준")
    st.dataframe(format_ranking(selected_rank), use_container_width=True, hide_index=True, height=500)

    st.subheader("기간별 성과 순위")
    tabs = st.tabs(list(LOOKBACKS))
    for tab, (label, days) in zip(tabs, LOOKBACKS.items()):
        with tab:
            try:
                st.dataframe(format_ranking(ranked_frame(universe, returns_lookback(prices, days))), use_container_width=True, hide_index=True, height=430)
            except ValueError as exc:
                st.warning(str(exc))

    composite = composite_ranking(universe, prices)
    with st.expander("4개 기간 평균 순위 (리더십 점수)"):
        leadership_table = composite[["sector", "ticker", "etf_name", "average_rank", "rank_movement"]].rename(columns={"sector": "섹터", "ticker": "ETF", "etf_name": "ETF 이름", "average_rank": "평균 순위", "rank_movement": "순위 변화 (6M → 1D)"})
        selection = st.dataframe(
            leadership_table,
            use_container_width=True,
            hide_index=True,
            key="leadership_ranking_table",
            on_select="rerun",
            selection_mode="single-row",
        )
        selected_rows = selection.selection.rows
        if selected_rows:
            st.session_state["selected_holdings_ticker"] = composite.iloc[selected_rows[0]]["ticker"]
        st.caption("행을 클릭하면 해당 ETF의 holdings를 아래에서 바로 표시합니다.")

    default_tickers = selected_rank["ticker"].head(4).tolist()
    chart_tickers = st.multiselect("차트에 표시할 ETF", tickers, default=default_tickers)
    if chart_tickers:
        st.subheader("선택 ETF 상대 성과")
        st.caption("마우스 휠: 확대/축소 · 드래그: 이동 · 차트 시작점은 0%")
        st.plotly_chart(normalized_chart(prices, chart_tickers, resolved_start, resolved_end), use_container_width=True, config={"scrollZoom": True, "displaylogo": False})

    if "selected_holdings_ticker" not in st.session_state:
        st.session_state["selected_holdings_ticker"] = chart_tickers[0] if chart_tickers else tickers[0]
    selected_ticker = st.selectbox("holdings를 볼 ETF", tickers, key="selected_holdings_ticker")
    row = universe.loc[universe["ticker"] == selected_ticker].iloc[0]
    st.subheader(f"{row.sector} · {selected_ticker} holdings")
    try:
        with st.spinner(f"{selected_ticker} 공식 holdings를 확인하는 중입니다…"):
            holdings, meta, stale = cached_holdings(selected_ticker, row.official_source)
        if stale:
            st.warning(meta.get("warning", "로컬 캐시를 표시합니다."))
        st.caption(f"기준일: {meta.get('as_of', '알 수 없음')} · 데이터: {meta.get('provider', '공식 원본')} · [운용사 공식 원본]({row.official_source})")
        top = holdings.head(10).copy()
        top["weight_pct"] = top["weight_pct"].map(lambda value: f"{value:.2f}%" if pd.notna(value) else "-")
        st.markdown("#### 상위 10개 보유종목")
        st.dataframe(top.rename(columns={"ticker": "티커", "company_name": "종목명", "weight_pct": "비중"}), use_container_width=True, hide_index=True)
        search = st.text_input("전체 holdings 검색", placeholder="티커 또는 종목명")
        full = holdings.copy()
        if search:
            mask = full["ticker"].str.contains(search, case=False, na=False) | full["company_name"].str.contains(search, case=False, na=False)
            full = full[mask]
        full["as_of"] = meta.get("as_of", "")
        full["official_source"] = row.official_source
        shown = full.rename(columns={"ticker": "티커", "company_name": "종목명", "weight_pct": "비중", "as_of": "기준일", "official_source": "공식 출처"})
        st.markdown(f"#### 전체 보유종목 ({len(shown):,}개)")
        st.dataframe(shown, use_container_width=True, hide_index=True, height=460)
        st.download_button("전체 holdings CSV 내려받기", shown.to_csv(index=False).encode("utf-8-sig"), file_name=f"{selected_ticker}_holdings.csv", mime="text/csv")
    except RuntimeError as exc:
        st.error(str(exc))
        st.link_button("운용사 공식 holdings 페이지 열기", row.official_source)

    st.divider()
    st.subheader(f"{row.sector} 관련 ETF 탐색 및 교집합")
    st.caption("Yahoo Finance는 ETF 후보 탐색에만 사용합니다. holdings와 교집합은 공식 운용사 원본을 읽는 데 성공한 ETF만 사용합니다.")
    search_key = f"related_candidates_{selected_ticker}"
    if st.button("관련 ETF 검색", key=f"search_{selected_ticker}"):
        try:
            with st.spinner("Yahoo Finance에서 ETF 후보를 검색하는 중입니다…"):
                st.session_state[search_key] = search_sector_etfs(row.sector)
        except Exception as exc:
            st.error(f"ETF 후보 검색 실패: {exc}")

    candidates = st.session_state.get(search_key)
    if candidates is not None and not candidates.empty:
        if selected_ticker not in candidates["ticker"].tolist():
            candidates = pd.concat([pd.DataFrame([{
                "ticker": selected_ticker, "etf_name": row.etf_name, "exchange": "fixed universe",
            }]), candidates], ignore_index=True)
        known_sources = universe.set_index("ticker")["official_source"].to_dict()
        verified_sources = {ticker: verified_official_source(ticker) for ticker in candidates["ticker"]}
        known_sources.update({ticker: source for ticker, source in verified_sources.items() if source})
        candidates = candidates.copy()
        candidates["official_source"] = candidates["ticker"].map(known_sources).fillna("")
        st.dataframe(candidates.rename(columns={"ticker": "ETF", "etf_name": "ETF 이름", "exchange": "거래소", "official_source": "확인된 공식 URL"}), use_container_width=True, hide_index=True)
        default_compare = [selected_ticker] if selected_ticker in candidates["ticker"].tolist() else []
        compare_tickers = st.multiselect("교집합을 계산할 ETF", candidates["ticker"].tolist(), default=default_compare, key=f"compare_{selected_ticker}")
        official_sources: dict[str, str] = {}
        for ticker in compare_tickers:
            preset = known_sources.get(ticker, "")
            official_sources[ticker] = st.text_input(f"{ticker} 공식 holdings URL", value=preset, key=f"source_{selected_ticker}_{ticker}")
        if st.button("선택 ETF 공식 holdings 갱신 및 교집합 계산", key=f"overlap_{selected_ticker}"):
            collected: dict[str, pd.DataFrame] = {}
            statuses = []
            for ticker in compare_tickers:
                source = official_sources[ticker].strip()
                if not source:
                    statuses.append({"ETF": ticker, "상태": "제외", "사유": "공식 holdings URL이 확인되지 않았습니다."})
                    continue
                try:
                    frame, meta, stale = get_holdings(ticker, source, refresh=True)
                    collected[ticker] = frame
                    statuses.append({"ETF": ticker, "상태": "캐시" if stale else "성공", "사유": meta.get("as_of", "기준일 없음")})
                except RuntimeError as exc:
                    statuses.append({"ETF": ticker, "상태": "제외", "사유": str(exc)})
            st.session_state[f"overlap_result_{selected_ticker}"] = (collected, statuses)

        result = st.session_state.get(f"overlap_result_{selected_ticker}")
        if result:
            collected, statuses = result
            st.markdown("#### 공식 holdings 수집 상태")
            st.dataframe(pd.DataFrame(statuses), use_container_width=True, hide_index=True)
            common, matrix = overlap_report(collected)
            st.markdown("#### 모든 선택 ETF의 공통 보유종목")
            if common.empty:
                st.info("공식 holdings 수집에 성공한 ETF들 사이에 공통 종목이 없거나, 비교 가능한 ETF가 2개 미만입니다.")
            else:
                st.dataframe(common, use_container_width=True, hide_index=True)
            if not matrix.empty:
                st.markdown("#### ETF 쌍별 공통 종목 수")
                st.dataframe(matrix, use_container_width=True)


if __name__ == "__main__":
    main()
