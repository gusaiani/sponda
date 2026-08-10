# CVM Ingestion · Implementation Plan

**Goal:** a company's quarterly figures are live in Sponda as close as possible to the day it files them.

That is a latency target, not a data-source preference. CVM is the means, not the end · we adopt it only where it shortens the path from filing to page. BRAPI stays the sole source of prices, market caps, dividends per share and the ticker universe, none of which CVM publishes.

## Where the latency actually is

Filing to pixel, today, decomposed:

| Hop | Mechanism | Cost |
|---|---|---|
| Issuer files (`DT_RECEB`) → BRAPI serves it | BRAPI's own ingestion | **7 to 21 days** (measured: Gerdau filed 2026-08-04, BRAPI still lacks it on 08-10) |
| BRAPI serves it → row in Sponda DB | `_ensure_fresh_data` on page view (24h staleness) or `refresh-fundamentals.timer` | ≤24h if someone views the page, else ≤7 days |
| DB row → API payload | `FUNDAMENTALS_CACHE_TTL = 24h` | ≤24h |
| API payload → browser | `Cache-Control: public, max-age=3600` at Cloudflare | ≤1h |

Worst case ≈ **23 days**. Best case ≈ 8 days. The provider hop dominates, but the two cache hops add a fixed 25 hours that no amount of faster ingestion can recover.

With CVM as the fast path and the caches fixed:

| Hop | Cost |
|---|---|
| Issuer files → present in CVM archive | ≤5 days observed, true figure unmeasured (see PR 1) |
| CVM archive → DB row | ≤24h (daily timer) |
| DB row → API payload | 0 (invalidate on write) |
| API payload → browser | 0 to 1h (purge or shorten TTL) |

Target ≈ **2 to 3 days**, floored by CVM's own publication cadence. Measuring that floor is the first task, because if CVM turns out to publish same-day the whole design should chase it, and if it publishes weekly the payoff shrinks and PR 5 is not worth building.

## Non-goals

- **No historical backfill from CVM.** Ten years of BRAPI-sourced statements already exist and are internally consistent. Mixing sources within one series risks step changes in the P/E10 denominator for no user-visible gain. CVM writes new quarters only.
- **No replacement of market data.** Prices, market caps, dividends per share, split factors and the B3 ticker list have no CVM equivalent. BRAPI remains load-bearing.
- **No US coverage.** CVM is Brazil only. The other ~18,000 tickers stay on FMP.

## PR sequence

### PR 1 · Measure before building

Two independent measurements, both cheap, both able to kill later PRs.

**1a. At-scale calibration.** `backend/quotes/management/commands/audit_cvm_vs_brapi.py`. For a quarter both sources already hold (2026-03-31), parse CVM for every mapped Brazilian ticker and diff all ten fields against the stored BRAPI values. Emit a CSV: ticker, field, cvm, brapi, delta, pct.

Precedent: n=2 (Gerdau, Petrobras) matched exactly across all ten fields, within R$1,000 of rounding on two. n=348 is the real test.

**Gate:** if disagreement on `net_income`, `stockholders_equity` or `operating_cash_flow` exceeds ~2% of tickers beyond rounding, stop and diagnose before PR 5. A CVM-primary path that silently disagrees with the existing series is worse than a slow one.

**1b. CVM publication lag.** Daily job snapshotting `itr_cia_aberta_<year>.csv` (the 180 KB index, not the 13 MB archive) into a small table: `(cvm_code, dt_refer, dt_receb, first_seen_at)`. After one earnings season this yields the true distribution of filing-to-archive lag.

**Gate:** if the median exceeds ~7 days, CVM buys little over BRAPI and PR 5 should be reconsidered.

Ships alone, runs for a full quarter while later PRs proceed.

### PR 2 · Close the 25-hour cache gap

Independent of everything above and worth doing regardless of whether CVM ever becomes primary.

- Invalidate `fundamentals:{ticker}`, `pe10:{ticker}`, `multiples_history:{ticker}`, `ticker_detail_{ticker}`, `ticker_peers_{ticker}` on any statement write. Today `seed_quarter_from_cvm` requires a manual shell to do this, which is a latent trap.
- Recompute `IndicatorSnapshot` for affected tickers in the same transaction, so the screener never disagrees with the detail page.
- Decide the Cloudflare edge: either add an API token to `/opt/sponda/.env` and purge by URL, or drop `max-age` on `/api/quote/*/fundamentals/` to something under 5 minutes. There are currently no Cloudflare credentials on the box.

Cuts up to 25 hours off every path, including the BRAPI one. Highest value per hour of work in the whole plan.

### PR 3 · The ticker bridge

CVM keys by `CD_CVM` and CNPJ, never by ticker. `TICKER_TO_CVM_CODE` hardcodes six entries; 348 are needed.

- Migration: `Ticker.cvm_code` (nullable, indexed) and `Ticker.cnpj`. In the database, not a Python dict, so corrections need no deploy.
- `map_tickers_to_cvm` command: normalise (uppercase, strip accents and punctuation, expand `BCO`→`BANCO`, drop `- EM RECUPERAÇÃO JUDICIAL`, unify `S.A.`/`SA`/`S/A`), then token-overlap score against `cad_cia_aberta.csv`. Auto-accept above a confidence threshold, write the remainder to a review CSV with the top three candidates each.
- Manual pass over the residue, then load the reviewed file.
- Monthly check that flags Brazilian tickers with market cap and no `cvm_code`, so IPOs surface rather than silently miss.

Exact-match baseline is 200/348 (57.5%). The 148 failures are all name-rendering drift, not missing companies: `BCO ABC BRASIL S.A.` vs `BANCO ABC BRASIL S/A`, `ALPARGATAS S.A.` vs `ALPARGATAS SA`, `AMERICANAS S.A` vs `AMERICANAS S.A. - EM RECUPERAÇÃO JUDICIAL`. Eleven tickers store no company name at all and need manual entry.

Tests: each real failure mode above as a fixture.

### PR 4 · Sector-aware accounts and a validation gate

The chart of accounts is sector-specific. `cvm.py` currently assumes the industrial taxonomy everywhere.

Measured across 416 consolidated filers for 2026: 404 report equity in `2.03`, 7 in `2.07`, 5 in `2.08`. Banco do Brasil's `2.03` is *Provisões*, R$39.11bn, against real equity of R$196.91bn in `2.07`. Equity is the denominator of `debtToEquity` and `liabilitiesToEquity`, so this corrupts displayed ratios rather than a label.

- Resolve equity by matching `DS_CONTA` ("Patrimônio Líquido Consolidado") rather than by account number.
- Detect taxonomy (industrial / financial / insurance) from the `3.01` label, and set `current_assets`, `current_liabilities` and `total_debt` to `None` for filers that do not report those concepts. Banks report by liquidity, not current/non-current, so `currentRatio` is undefined for them rather than wrong.
- `revenue` stays best-effort: `3.01` means *Receitas de Intermediação Financeira* for banks, but nothing in `indicators.py` or `pe10.py` reads revenue · it is a display column only, so a mislabelled bank revenue is cosmetic.
- **Validation gate before any write:** assets must equal liabilities plus equity, and equity must be within an order of magnitude of the prior quarter. Refuse the row and log loudly on failure. The failure mode here is a plausible wrong number, which is exactly what survives into production unnoticed.

Tests: Banco do Brasil and an insurer as real fixtures alongside the existing industrial ones.

### PR 5 · Continuous ingestion

`sync_cvm_filings` plus `sponda-sync-cvm.timer`, daily.

- Read the index CSV first (180 KB). Only when it lists a `DT_RECEB` newer than last seen does the run download the 13 MB archive.
- For each newly filed company: resolve ticker via `Ticker.cvm_code`, parse, validate (PR 4), write only quarters BRAPI does not already have.
- Migration: `source` column on `QuarterlyEarnings`, `QuarterlyCashFlow`, `BalanceSheet` (`brapi` / `fmp` / `cvm`). Without provenance there is no way to audit a disagreement or roll back a bad parse.
- Precedence: BRAPI still wins on conflict, since its rows are the ten-year baseline. CVM fills gaps only. Revisit once PR 1a's numbers are in.
- `MonitoredCommand` with a Sentry monitor slug, matching the other timers.

### PR 6 · Q4 via DFP

ITR covers Q1 to Q3 only. Q4 lives in the annual DFP, filed the following March and audited.

- Extend `cvm.py` to the DFP archive (confirmed available back to 2010). Q4 flows = annual minus the nine-month YTD from the Q3 ITR; the 31 December balance sheet comes straight from the DFP.
- The DFP restates unaudited quarters, so landing one must reprocess Q1 to Q3 of that year, not merely append Q4.

Last in sequence: Q4 filings arrive in March, well outside the window this plan is optimising.

### PR 7 · The goal as a number

Record `filed_at` (`DT_RECEB`) alongside each CVM-sourced row and publish a single metric: **median days from filing to live**. Without it, "as near their quarterly publishing dates as possible" is an aspiration rather than something that can regress and be noticed.

## Sequencing and effort

| PR | Depends on | Estimate |
|---|---|---|
| 1 · Measure | none | 0.5 day, then one quarter of observation |
| 2 · Cache gap | none | 0.5 day |
| 3 · Ticker bridge | none | 1 day, plus manual review of ~150 pairs |
| 4 · Sector taxonomy | none | 1 day |
| 5 · Continuous ingestion | 1a, 3, 4 | 1 day |
| 6 · Q4 via DFP | 5 | 1 day |
| 7 · Metric | 5 | 0.5 day |

Roughly **5.5 days**. PRs 1, 2, 3 and 4 are mutually independent and can land in any order.

Start with 2. It is half a day, needs nothing else, and removes 25 hours of latency from every ticker in the system including the US ones.

## Risks

| Risk | Mitigation |
|---|---|
| CVM and BRAPI disagree at scale | PR 1a gates PR 5 before any dependency is built on the assumption |
| Silent wrong values for banks and insurers | PR 4's balance and continuity checks refuse the write rather than log a warning |
| CVM's lag turns out no better than BRAPI's | PR 1b measures it against real filings before PR 5 is written |
| Ticker map rots as companies rename or list | Stored in DB, monthly unmapped-ticker report |
| CVM changes the archive layout | Real-filing fixtures in tests; the command fails loudly rather than writing nulls |
| Mixed-source series drift | `source` column plus no historical backfill · CVM writes only quarters BRAPI lacks |
