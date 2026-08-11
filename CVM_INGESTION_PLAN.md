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
| Issuer files → included in the next archive rebuild | ~2 days observed |
| Archive rebuild cadence | **the binding constraint** · likely weekly, see below |
| CVM archive → DB row | ≤1h (hourly poll, PR 1b) |
| DB row → API payload | 0 (invalidate on write · **done**, PR 2) |
| API payload → browser | ≤5 min (**done**, PR 2) |

Target ≈ **3 to 4 days median, 7 worst case**, floored entirely by CVM's rebuild cadence.

### What PR 1b already established (2026-08-11)

- All six CVM document datasets (ITR, DFP, FCA, IPE, VLMO, FRE) carried the same `Last-Modified` of Sunday 2026-08-09, 10:00–11:40 GMT · one batch rebuild across the tree. It was untouched through Monday and Tuesday, while the separately-built company registry was stamped that Tuesday. This points to a **weekly Sunday** cadence, inferred from a single 2-day gap · a hypothesis, not a finding.
- Within a build the publication lag is short: the newest filing was 2 days old, with 52 filings each at 3 and 4 days.
- The archive honours `If-None-Match` (304, 0 bytes) and `Accept-Ranges`, so the index can be polled hourly for nothing and read from a 256 KB ranged fetch rather than 12 MB.

**This downgrades the plan's original promise.** A 2-day publication lag matters little if the archive is only rebuilt weekly: a filing received the day after a rebuild waits for the next one however often it is polled. Against BRAPI's measured 7–21 days that is a halving, not the near-elimination the 2-day figure alone suggests. PR 1b's gate (reconsider if the median exceeds ~7 days) still passes, so PR 5 survives with a smaller prize.

### A correction to the original design

PR 5 below proposed reading "the index CSV first (180 KB)" and downloading the archive only when it changed. **There is no standalone index file** · it exists only as the first entry inside the zip. The conditional-request and byte-range mechanics above replace that idea and are strictly cheaper: zero bytes on an unchanged poll rather than 180 KB.

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

**1b. CVM publication lag · SHIPPED.** `snapshot_cvm_filings` polls the archive hourly, recording each distinct build (`CvmArchiveBuild`) and each filing with the build that first carried it (`CvmFiling`). `report_cvm_lag` summarises rebuild cadence and publication lag. An unchanged poll costs one HEAD request; a changed one reads the index from a 256 KB ranged fetch.

Hourly rather than daily because the rebuild cadence is the quantity being measured, and a daily poll would only locate a rebuild to within 24 hours.

**Backfill is excluded from the measurement.** The first poll records everything published that year so far, attributed to whatever build was current · counting that gap as lag would have reported a median of 87 days on day one. A lag counts only when the filing first appeared in a build *later* than the earliest one recorded, so an observation exists that could have carried it and did not. Note this is deliberately not a test on the receipt date: a filing received before polling began but absent from the first observed build was still watched into existence, and those are exactly the slow ones · excluding them would bias the distribution toward flattering the CVM.

**Gate:** if the median exceeds ~7 days, CVM buys little over BRAPI and PR 5 should be reconsidered.

Timing: the Q2 deadline is 2026-08-14 and the archive held only 196 of ~662 expected Q2 filings (29.6%) on 08-11, so roughly 70% of Brazilian issuers file into the Sunday 08-16 rebuild. That is the single most informative observation of the year, which is why this shipped before PRs 3 and 4.

### PR 2 · Close the 25-hour cache gap · SHIPPED

Independent of everything above and worth doing regardless of whether CVM ever becomes primary.

- Invalidate `fundamentals:{ticker}`, `pe10:{ticker}`, `multiples_history:{ticker}`, `ticker_detail_{ticker}`, `ticker_peers_{ticker}` on any statement write. Today `seed_quarter_from_cvm` requires a manual shell to do this, which is a latent trap.
- Recompute `IndicatorSnapshot` for affected tickers in the same transaction, so the screener never disagrees with the detail page.
- Decide the Cloudflare edge: either add an API token to `/opt/sponda/.env` and purge by URL, or drop `max-age` on `/api/quote/*/fundamentals/` to something under 5 minutes. There are currently no Cloudflare credentials on the box.

Cuts up to 25 hours off every path, including the BRAPI one. Highest value per hour of work in the whole plan.

### PR 3 · The ticker bridge · SHIPPED

CVM keys by `CD_CVM` and CNPJ, never by ticker. `TICKER_TO_CVM_CODE` hardcoded six entries; 361 were needed.

**The plan's premise here was wrong.** It assumed the bridge had to be built by fuzzy name matching (200/348 exact, ~150 pairs reviewed by hand). CVM publishes the mapping directly: the FCA securities table (`fca_cia_aberta_valor_mobiliario_<year>.csv`, inside a ~350 KB annual zip) carries `Codigo_Negociacao` — the B3 ticker — against a CNPJ, and the registry maps CNPJ to `CD_CVM`. No fuzzy matching required for the large majority.

Three strategies, strongest first, each declining on ambiguity:

| Method | Evidence | Covers |
|---|---|---|
| `ticker` | FCA's published trading code | 361 |
| `root` | The four-letter B3 root, when FCA lists only the unit (`KLBN11` → `KLBN3`/`KLBN4`) | 12 |
| `name` | Normalised company name against the registry | 14 |
| `manual` | `--set`, validated against the registry; never overwritten | 2 |

**358 of 361 resolve from published data alone (99.2%)**, against the plan's budget of ~150 manual pairs. The three that fail are exactly the three storing no company name, so the name fallback has nothing to work with. Two were identified from the registry by hand; `WDCN3` matches no registered company at all.

**The published field is dirty and must be validated.** 61 of the `Codigo_Negociacao` values are not tickers: zeros, a debenture code `1545-8`, and for CSN its own CVM code `4030` in the ticker column. Unvalidated, that attaches real tickers to whichever company published the string. CSN is rejected as a ticker and then recovered correctly by name.

Verified against an independent dataset: 355 of 369 mapped tickers share a distinctive name token with the company that actually filed. All 14 exceptions came from the authoritative `ticker` method and are stale names on our side (Odontoprev → BradSaúde, Marfrig → MBRF), not bad mappings. All six hardcoded pairs from PR #284 reproduce exactly.

Also stored: `Ticker.cvm_code`, `cnpj`, `cvm_match_method`. In the database, not a Python dict, so corrections need no deploy · and provenance is what a disputed figure gets traced back through.

Monthly timer flags Brazilian tickers **with a market cap** and no code, so IPOs surface. The market-cap filter matters: around a dozen BDRs (`XPBR31`, `PRXB31`, `INBR32`) match the B3 shape but are receipts over foreign issuers CVM never registers, so they can never be mapped and would otherwise bury a real new listing under permanent noise.

Known limitation: a BDR sharing a root with a Brazilian issuer (`JBSS32` over JBS N.V. vs `JBSS3` for JBS S.A.) root-matches to the Brazilian entity. None are currently in the universe; the `root` provenance flags it for audit.

### PR 4 · Sector-aware accounts and a validation gate

The chart of accounts is sector-specific. `cvm.py` currently assumes the industrial taxonomy everywhere.

Measured across 416 consolidated filers for 2026: 404 report equity in `2.03`, 7 in `2.07`, 5 in `2.08`. Banco do Brasil's `2.03` is *Provisões*, R$39.11bn, against real equity of R$196.91bn in `2.07`. Equity is the denominator of `debtToEquity` and `liabilitiesToEquity`, so this corrupts displayed ratios rather than a label.

- Resolve equity by matching `DS_CONTA` ("Patrimônio Líquido Consolidado") rather than by account number.
- Detect taxonomy (industrial / financial / insurance) from the `3.01` label, and set `current_assets`, `current_liabilities` and `total_debt` to `None` for filers that do not report those concepts. Banks report by liquidity, not current/non-current, so `currentRatio` is undefined for them rather than wrong.
- `revenue` stays best-effort: `3.01` means *Receitas de Intermediação Financeira* for banks, but nothing in `indicators.py` or `pe10.py` reads revenue · it is a display column only, so a mislabelled bank revenue is cosmetic.
- **Validation gate before any write:** assets must equal liabilities plus equity, and equity must be within an order of magnitude of the prior quarter. Refuse the row and log loudly on failure. The failure mode here is a plausible wrong number, which is exactly what survives into production unnoticed.

Tests: Banco do Brasil and an insurer as real fixtures alongside the existing industrial ones.

### PR 5 · Continuous ingestion

`sync_cvm_filings` plus `sponda-sync-cvm.timer`.

- Trigger off `CvmFiling` rows created by PR 1b's poll rather than re-deriving what is new · the index read, conditional request and dedup already exist there. Only when a *mapped* ticker has a new filing does the run download the 12 MB archive.
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

| PR | Depends on | Estimate | Status |
|---|---|---|---|
| 1a · At-scale calibration | 3, in practice | 0.5 day | Blocked · needs the ticker bridge to reach n=348 |
| 1b · Publication lag | none | 0.5 day, then observation | **Shipped**, accruing observations |
| 2 · Cache gap | none | 0.5 day | **Shipped** |
| 3 · Ticker bridge | none | 1 day, plus manual review of ~150 pairs | **Shipped** · 99.2% from published data, 2 pairs by hand |
| 4 · Sector taxonomy | none | 1 day | Next |
| 5 · Continuous ingestion | 1a, 1b, 3, 4 | 1 day | |
| 6 · Q4 via DFP | 5 | 1 day | |
| 7 · Metric | 5 | 0.5 day | |

Roughly **4.5 days** remaining. PRs 3 and 4 are mutually independent.

1a was listed as depending on nothing, which was wrong: it calibrates "every mapped Brazilian ticker", and only six are mapped. Its exact-match baseline of 200/348 is reachable without PR 3, but the full n=348 run needs the bridge, so 3 should come first.

## Risks

| Risk | Mitigation |
|---|---|
| CVM and BRAPI disagree at scale | PR 1a gates PR 5 before any dependency is built on the assumption |
| Silent wrong values for banks and insurers | PR 4's balance and continuity checks refuse the write rather than log a warning |
| CVM's lag turns out no better than BRAPI's | PR 1b measures it against real filings before PR 5 is written · early evidence says the rebuild cadence, not the publication lag, is the constraint |
| A backfill is mistaken for a measurement | Lag counts only for filings that first appeared in a build later than the earliest recorded one; everything else is reported as backfill, and an empty sample prints "not enough observations yet" rather than a number |
| Ticker map rots as companies rename or list | Stored in DB, monthly unmapped-ticker report filtered to tickers with a market cap |
| A ticker is mapped to the wrong company | Every strategy declines on ambiguity; `Codigo_Negociacao` is validated against the B3 shape before use; `cvm_match_method` records the evidence so a disputed figure is traceable |
| CVM changes the archive layout | Real-filing fixtures in tests; the command fails loudly rather than writing nulls |
| Mixed-source series drift | `source` column plus no historical backfill · CVM writes only quarters BRAPI lacks |
