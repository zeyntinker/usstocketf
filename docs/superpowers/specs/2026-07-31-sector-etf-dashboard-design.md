# Sector ETF Leadership Dashboard — Design

## Goal

Build a free, locally running Windows application inspired by the supplied lecture. It monitors a fixed universe of 42 sector and thematic ETFs, ranks their performance, visualizes selected ETFs, and exposes the official holdings of a selected ETF.

The app is for the owner's personal research. It does not produce buy/sell signals, price targets, or an investment disclaimer.

## Fixed ETF universe

The universe is fixed in `data/universe.csv`. Every row contains the sector label, ticker, ETF name, and official issuer holdings source. The 42 approved tickers are:

`ITA, DBA, AIQ, JETS, KBE, XLB, XBI, PKB, ICLN, SKYY, DBC, XLY, XLP, BLOK, KARS, XLE, ESPO, XLF, PBJ, ITB, XLI, PAVE, KIE, PEJ, LIT, IHI, XME, FCG, URA, PPH, QTUM, IYR, XRT, SOXX, BOAT, IGV, TAN, SLX, IYZ, WOOD, IYT, XLU`.

## Architecture

- `app.py` renders the Streamlit dashboard and owns UI events.
- `services/prices.py` downloads adjusted daily closes from Yahoo Finance and maintains a local price cache.
- `services/ranking.py` calculates returns and ranks.
- `services/holdings.py` downloads and normalizes official issuer holdings data and maintains a local holdings cache.
- `data/universe.csv` is the source of truth for the fixed ETF universe and official holdings endpoints.
- `launcher/` contains the Windows launcher that opens a dedicated app window and shuts down its matching Streamlit process on exit.

The app fetches or reuses prices, computes rankings, and renders the chart/table. Selecting an ETF triggers a holdings refresh or cache fallback.

## Ranking rules

- The preset lookbacks are 21, 42, 63, and 126 trading days (displayed as 1, 2, 3, and 6 months).
- Returns use adjusted closing prices: `(ending adjusted close / starting adjusted close - 1) * 100`.
- The default leadership measure is the equal-weighted average of the four individual period ranks.
- Every individual-period and custom-period table displays all 42 ETFs, sorted by return descending.
- A custom start date maps to the first available trading day on or after it. A custom end date maps to the last available trading day on or before it. The resolved dates are shown in the UI.

## UI

The application uses a dark financial-dashboard theme.

- The sidebar provides preset/custom date controls, a multi-select ETF picker, and a refresh command.
- A Plotly normalized-return chart shows only the chosen ETFs; the start is 0%. It supports mouse-wheel zoom, drag pan, range selection, and hover values.
- The ranking area shows all 42 ETFs, return percentages, and ranks in descending performance order.
- The selected ETF detail area includes an upper top-10 holdings summary and a complete holdings table with ticker, company name, weight, as-of date, and official source. It supports searching, sorting, and CSV download.
- The selected ETF is shared between ranking, chart, and holdings views.

## Data integrity and failures

- Holdings are obtained from the issuer's official CSV/XLSX/data endpoint first. HTML scraping is used only where an issuer provides no structured official source.
- A successful response is cached with its source URL and as-of date.
- If a refresh fails, the app displays the latest successful cache and labels its actual date.
- If no cache exists, the app displays a clear failure state and an official-source link; it never substitutes unofficial or invented holdings.
- Price download failures follow the same cache-first pattern. Ranking views identify stale data rather than presenting it as current.

## Local execution and exit

- `setup.bat` installs dependencies.
- A desktop shortcut starts a dedicated browser app window and its local Streamlit server.
- The in-app exit button terminates only that dedicated window and its launched local server; it does not close ordinary browser sessions.

## Verification

- Unit tests use deterministic fixture prices to verify trading-day resolution, return calculation, rank ordering, and the presence of 42 rows.
- Holdings parser tests use saved official-file fixtures to verify normalization of ticker, name, weight, as-of date, and source.
- Manual smoke testing verifies launch, interactive chart zoom/pan, custom-date ranking, selection synchronization, holdings download/cache fallback, and complete exit behavior.
