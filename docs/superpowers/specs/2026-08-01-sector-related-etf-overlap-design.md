# Sector-Related ETF Discovery and Holdings Overlap

## Objective

For the sector of the ETF selected in the dashboard, discover candidate U.S.-listed ETFs through Yahoo Finance search, let the user choose candidates, retrieve only verified official holdings, and show holdings intersections.

## Discovery

- Search Yahoo Finance using the English sector label plus `ETF`.
- Retain results identified as U.S.-listed ETFs.
- The user checks the candidates that form the comparison set; search results alone never trigger holdings collection.

## Official holdings

- Each selected ETF uses a provider-specific official CSV, XLSX, or documented official endpoint adapter.
- Adapters standardize ticker, name, CUSIP, ISIN, weight, as-of date, and source URL.
- Collection runs only when the user presses the explicit refresh button and is cached locally with source and as-of metadata.
- No inferred, simulated, unofficial, or name-derived holdings may be displayed.
- If an official source cannot be read, the ETF is excluded from overlap calculation and the UI reports the failure and official source link.

## Intersection logic

- Match by CUSIP first, then ISIN, then an exactly matching normalized U.S. ticker.
- Do not use company-name similarity for matching.
- Display: (1) holdings common to every successfully collected selected ETF, including each fund weight and as-of date; (2) a pairwise ETF overlap-count matrix.

## UI and verification

- Add a related-ETF panel under the selected ETF's existing holdings section.
- Show candidate selection, explicit official-refresh action, per-ETF source status, common-holdings table, and pairwise matrix.
- Test search filtering, adapter normalization, strict matching precedence, cache fallback, failure exclusion, and no-overlap results.
