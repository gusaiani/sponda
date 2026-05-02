# Cross-Currency Indicators Fix Plan

Foreign-domiciled tickers (ADRs like NVO, TM, ASML, BABA) have their valuation indicators silently broken because Sponda mixes two currencies in the same calculation. This document explains the bug, quantifies the damage, and lays out the planned fix.

## The bug in one sentence

For any company that lists in one currency but files financials in another, Sponda divides a USD market cap by statement values denominated in the home currency (DKK, JPY, EUR, etc.), which is dimensionally meaningless and produces ratios that are off by the FX rate.

## How it happens

1. `fmp.fetch_quote` returns `marketCap` priced in the **listing currency** (USD for ADRs on NYSE/NASDAQ).
2. `fmp.fetch_income_statements`, `fetch_cash_flow_statements`, `fetch_balance_sheets` return values in `reportedCurrency` · the **filing currency** of the parent company. For Novo Nordisk this is DKK; for Toyota it is JPY; for ASML it is EUR.
3. We persist statement values as raw `BigIntegerField`s (`QuarterlyEarnings.net_income`, `QuarterlyCashFlow.free_cash_flow`, `BalanceSheet.stockholders_equity`, etc.) with no currency tag.
4. Indicator calculators (`calculate_pe10`, `calculate_pfcf10`, `peg`, `pfcf_peg`, `multiples_history`) divide market cap by statement values without converting either side. The result is `USD / DKK`, which is not a real ratio.

Same-currency ratios are unaffected: `debt / equity`, `liabilities / equity`, `current ratio`, `debt / avg earnings`, `debt / avg FCF` all read both numerator and denominator from statements in the same currency, so the unit cancels.

## Magnitude · NVO worked example

USD/DKK ≈ 6.85 at the time of writing.

| Indicator               | Sponda computes | Reality | Off by  |
|-------------------------|-----------------|---------|---------|
| PE5 (5-yr avg earnings) | 2.50            | 17.11   | ~6.85×  |
| PFCF5                   | 3.46            | 23.69   | ~6.85×  |

NVO appears in the screener as one of the cheapest large-caps in the database. The signal is pure currency artifact.

## Scope · 13 of 20 sampled ADRs are affected

| Reporting currency | Tickers (sample)               | Approx distortion |
|--------------------|--------------------------------|-------------------|
| JPY                | TM, SONY, MUFG                 | ~150× (PE looks ~0.1 instead of ~15) |
| TWD                | TSM                            | ~32×              |
| DKK                | NVO                            | ~7×               |
| CNY                | BABA, NIO                      | ~7×               |
| EUR                | ASML, SAP, SPOT, STLA, UL      | ~1.05×            |
| GBP                | BTI                            | ~0.79× (looks more expensive than it is) |
| USD                | NVS, AZN, SHOP, RIO, BP, HSBC, SE | OK             |

The screener is unusable when sorting by PE10/PFCF10 ascending: foreign ADRs flood the top because their ratios are artificially compressed by the FX factor.

## Frontend display, separate but related issue

`frontend/src/utils/format.ts::currencySymbol(ticker)` returns `"$"` for any non-Brazilian ticker. The Fundamentos tab therefore shows raw DKK/JPY/EUR values prefixed with a dollar sign. This compounds the misleading impression even when the underlying values are not used in a ratio.

## Architecture decision · compute in the statement currency

The cleanest fix is to translate **market cap into the statement currency** at the appropriate date, then divide. Reasons:

- Ratios are dimensionless; either currency works as long as both sides match. Picking the statement currency is more natural because the statement values are the source of truth and where inflation adjustment lives.
- FMP themselves do this: `/stable/key-metrics` for NVO returns `marketCap = 1.44T` (DKK) so all their ratios stay self-consistent.
- Absolute values (revenue, FCF, equity) keep their native units for display; users see "kr. 102 B revenue" instead of pretending DKK is USD.

## Implementation plan · five PRs

Each PR is independently shippable and reversible. Behavior does not change for end users until PR 3.

### PR 1 · Persist reporting currency

- Add `Ticker.reported_currency CharField(max_length=3)`. Migration.
- FMP sync writes the value back from the latest income statement on every refresh.
- BRAPI sync defaults to `"BRL"` for Brazilian tickers.
- Tests cover the new field and the sync writeback. No behavior change.

### PR 2 · FX rate model and sync

- New `FxRate(date, base_currency, quote_currency, rate)` model. Unique on `(date, base, quote)`. Index on `(base, quote, -date)` for "latest rate ≤ date" lookups.
- Management command `sync_fx_rates --currencies DKK,EUR,JPY,CNY,TWD,GBP,...` pulls daily USD↔X from FMP `/stable/historical-price-eod/full?symbol=USDDKK` etc., back to 2010.
- Helper `get_fx_rate(date, from_ccy, to_ccy)` returns the nearest rate (latest available ≤ date), pivoting via USD when needed. Returns `None` when data is missing.
- Daily systemd timer to keep recent rates fresh; weekly sweep over the universe to discover any new reporting currencies.
- Tests cover lookup, USD pivot, missing-rate fallback. Still no behavior change.

### PR 3 · Translate market cap in the indicator calculators

This is where behavior changes for foreign ADRs.

- New helper `market_cap_in_reported_currency(market_cap_usd, ticker, on_date)` looks up `Ticker.reported_currency`, fetches the FX rate for that date, returns the translated value. Returns `None` (rendered as "indicador indisponível") when FX data is missing, so the screener degrades gracefully.
- Wire the helper into `calculate_pe10`, `calculate_pfcf10`, `peg`, `pfcf_peg`, and `multiples_history`. The multiples-history chart uses the historical year-end FX rate per year, matching the year-end price already used for that year.
- **Inflation adjustment policy:**
  - BRL-reporting tickers · IPCA (unchanged)
  - USD-reporting tickers · USCPI (unchanged)
  - Everything else · **no inflation adjustment**, computed as nominal averages over the rolling window
  - **Everything else · per-country CPI** sourced via FMP (Denmark CPI for DKK, Japan CPI for JPY, Eurozone HICP for EUR, etc.). One series per reporting currency, fetched and persisted alongside USCPI/IPCA. Same monthly cadence and inflation-factor mechanics; only the source series changes.
- Tests cover NVO, TM, ASML, plus a "FX missing → None" degradation path and a "country-CPI missing → fall back to nominal" path.

### PR 4 · Frontend currency display

- Backend API returns `reportedCurrency` on the `fundamentals` and `pe10`/company-metrics endpoints.
- `frontend/src/utils/format.ts::currencySymbol` accepts an explicit reported-currency code. Map ISO → display symbol: DKK→"kr.", EUR→"€", JPY→"¥", GBP→"£", CNY→"¥", TWD→"NT$", USD→"$", BRL→"R$". Long-tail currencies fall back to the ISO code in italics.
- Company header shows both currencies when they differ: `NVO · USD (reports in DKK)`.
- **Missing historical FX:** the multiples-history chart applies the most recent available FX rate uniformly across all historical years, and renders a user-visible warning ribbon on the chart explaining that historical multiples use today's exchange rate. Same warning surfaces on PE10/PFCF10 cards when any historical year fell back to current-FX.
- Tests cover the new helper signature, the header rendering, and the warning visibility.

### PR 5 · Backfill and audit

- One-shot management command `audit_currencies` lists every Ticker by `(listing_currency, reported_currency)` pair, counts how many lack FX coverage, and flags any sync inconsistencies.
- Re-run `refresh_snapshot_fundamentals` for the full universe so the screener picks up the corrected PE10/PFCF10 values.
- Spot-check the 20 ADRs from the original survey to confirm.
- Update the screener documentation in the main README to mention the per-currency methodology and the inflation-adjustment caveat.

## Deferred work · with rationale

| Item | Why parked |
|---|---|
| Cross-listed tickers (ASML.AS vs NYSE ASML) | One row per US listing in the current schema; not changing for this fix. |
| Single-currency portfolio yield view (dividends across reporting currencies) | Separate feature; out of scope. |

## Decisions locked in

1. **FX source · FMP.** Already paid-for, has the historical depth (back to 2010+) we need for the multiples-history chart.
2. **Inflation adjustment · per-country CPI.** PR 3 wires up Denmark/Japan/Eurozone/etc. CPI series via FMP, same mechanics as the existing USCPI/IPCA paths. No reporting currency falls back to nominal.
3. **Missing historical FX · uniform current-FX with warning.** When historical FX rates are unavailable for some years in the multiples-history chart, apply the most recent FX uniformly across the missing years and render a visible warning to users so they understand the limitation.
