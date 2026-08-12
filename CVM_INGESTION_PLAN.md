# CVM Ingestion · Implementation Plan

**Goal:** a company's quarterly figures are live in Sponda as close as possible to the day it files them.

That is a latency target, not a data-source preference. CVM is the means, not the end · we adopt it only where it shortens the path from filing to page. BRAPI stays the sole source of prices, market caps, dividends per share and the ticker universe, none of which CVM publishes.

> **All seven PRs shipped.** What to check and when · including the first
> real filing-to-live measurement, due from the rebuild after the
> 2026-08-14 Q2 deadline · is in [`CVM_RUNBOOK.md`](CVM_RUNBOOK.md).

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

### PR 4 · Sector-aware accounts and a validation gate · SHIPPED

The chart of accounts is sector-specific. `cvm.py` assumed the industrial taxonomy everywhere.

**The problem was broader than equity.** Four account numbers hold different quantities for a bank:

| Account | Industrial filer | Banco do Brasil |
|---|---|---|
| `1.01` | Ativo Circulante | Caixa e Equivalentes de Caixa |
| `2.01` | Passivo Circulante | Passivos Financeiros a Valor Justo |
| `2.02.01` | Empréstimos e Financiamentos | **Depósitos** |
| `2.03` | Patrimônio Líquido | **Provisões** |

So `total_debt` was counting customer deposits as borrowings, and equity read R$39.11bn against a real R$196.91bn.

**The fix is narrower than this plan proposed.** Detecting taxonomy from the `3.01` label and branching turned out to be unnecessary: trusting an account number *only when its own label agrees* handles every case, and naturally yields `None` for a concept a filer does not report. It also catches what a sector rule would miss · three filers publish "Capitalização" at the borrowings account, one publishes "Depósitos Interfinanceiros" at the lease account, and the two insurers **do** report current/non-current, so branching on sector would have wrongly discarded their figures.

Equity is found by the line labelled "Patrimônio Líquido Consolidado", which all 416 filers carry despite placing it at `2.03` (404), `2.07` (7) or `2.08` (5).

`total_liabilities` is now the balance-sheet total less equity. It agrees with `2.01 + 2.02` for all 404 industrial filers, preserving PR #284's BRAPI calibration, and unlike that sum is meaningful for a bank.

`revenue` stays best-effort: `3.01` means *Receitas de Intermediação Financeira* for banks, but nothing in `indicators.py` or `pe10.py` reads revenue · it is a display column only.

**Validation gates**, all refusing rather than warning: assets must equal liabilities plus equity (held for 414 of 414, so a violation means the parse is wrong); two lines claiming to be equity is refused rather than guessed; and equity must stay within an order of magnitude of the prior quarter, checked in the writer where prior quarters exist.

Measured over the full 2026 archive: **416 of 416 filers parse, none refused.** Equity and total liabilities resolve for 415, current assets/liabilities for 403, debt and leases for 401. Gerdau and Petrobras reproduce their previously calibrated figures exactly.

### PR 5 · Continuous ingestion

`sync_cvm_filings` plus `sponda-sync-cvm.timer`, four times a day · SHIPPED.

- Triggers off `CvmFiling` rows created by PR 1b's poll rather than re-deriving what is new. Deciding there is nothing to write is one query rather than a 12 MB download, which is the normal state between seasons.
- For each newly filed company: resolve ticker via `Ticker.cvm_code`, parse, validate (PR 4), write only quarters no other source holds. The archive is fetched once per run and parsed once per company, then written to every ticker sharing that CVM code.
- `source` column on `QuarterlyEarnings`, `QuarterlyCashFlow`, `BalanceSheet`. **A writer stamps its own source** · adding the column without adding it to BRAPI's `bulk_create(update_fields=...)` would have let BRAPI overwrite the figures while the row still claimed `cvm`, which is worse than no provenance at all.
- Existing rows are deliberately **not** backfilled. Their origin is inferable but not known, and some were seeded from CVM by hand, so labelling from a guess would make the audit trail assert something false. Empty means unrecorded, which is what happened.
- Precedence: BRAPI wins, including for rows whose provenance predates the column · absence of a label is not permission to overwrite. When BRAPI catches up it overwrites the CVM row and restamps it, which is the intended end state.
- Failure is local: a company that fails to parse or is refused by the continuity gate is reported and skipped, since one bad filing during earnings season must not cost the batch.
- `MonitoredCommand` with a Sentry monitor slug, matching the other timers.

The write path is shared with the manual seeder (`quotes/cvm_writer.py`) so both go through the same gates rather than drifting.

### PR 6 · Q4 via DFP · SHIPPED

ITR covers Q1 to Q3 only. Q4 lives in the annual DFP, filed the following March and audited.

- `cvm.py` extended to the DFP archive. Both archives publish the same five statement files under different prefixes, so the account mapping, label guards and balance checks apply unchanged.
- Q4 flows = the audited year minus the nine months already reported. The 31 December balance sheet comes straight from the DFP · a snapshot is not differenced.
- Only the calendar-year window counts. Filers on non-calendar fiscal years publish trailing-twelve-month windows against the same document, and taking any twelve-month window would mix a March-ending year into a December one.

**The plan said landing Q4 must reprocess Q1 to Q3 rather than merely append. It does not, deliberately.** The audit adjustment is charged wholly to Q4, so the four quarters sum to the audited year, and BRAPI's series is never displaced.

That decision rests on measurement rather than preference. BRAPI carries restated figures: across the ten Q1 2026 filings CVM shows as restated, BRAPI's stored net income matched CVM's restated value **9 of 9**. Restatements are 3.6% of filings (30 of 827). Since the weekly `refresh_snapshot_fundamentals` re-syncs the full history and overwrites on `(ticker, end_date)`, a restatement reaches us within a week without intervention. There is nothing to gain by breaking the invariant.

**A bound on the implied quarter's size would be dead code and is deliberately absent.** The implied value is the year minus the nine months, so its magnitude can never exceed their sum; any threshold loose enough to admit a genuine collapse is unreachable. What is refused instead: an annual reporting no net income (three 2025 filers published zero against quarters worth billions), and any company missing one of Q1 to Q3.

A year that quietly disagrees with its own quarters stays undetectable here · AUAU3 and BOBR4 differ from theirs by 63% and 36%, visible only against a Q4 from another source. `source` is what makes those auditable.

Measured against 2025: of 279 companies where a Q4 could be derived, **277 (99.3%) matched the Q4 BRAPI eventually published**, within 1%. Three refused by the gate; the two that differed are the pair above.


### PR 7 · The goal as a number

Record `filed_at` (`DT_RECEB`) alongside each CVM-sourced row and publish a single metric: **median days from filing to live**. Without it, "as near their quarterly publishing dates as possible" is an aspiration rather than something that can regress and be noticed.

## Sequencing and effort

| PR | Depends on | Estimate | Status |
|---|---|---|---|
| 1a · At-scale calibration | 3 | 0.5 day | **Gate PASSED** at n=347 |
| 1b · Publication lag | none | 0.5 day, then observation | **Shipped**, accruing observations |
| 2 · Cache gap | none | 0.5 day | **Shipped** |
| 3 · Ticker bridge | none | 1 day, plus manual review of ~150 pairs | **Shipped** · 99.2% from published data, 2 pairs by hand |
| 4 · Sector taxonomy | none | 1 day | **Shipped** · label-guarded, no sector branching needed |
| 5 · Continuous ingestion | 1a, 1b, 3, 4 | 1 day | **Shipped** |
| 6 · Q4 via DFP | 5 | 1 day | **Shipped** |
| 7 · Metric | 5 | 0.5 day | **Shipped** |

Roughly **3 days** remaining, all of it now on the critical path: 1a gates PR 5, and PRs 6 and 7 follow it.

1a was listed as depending on nothing, which was wrong: it calibrates "every mapped Brazilian ticker", and only six are mapped. Its exact-match baseline of 200/348 is reachable without PR 3, but the full n=348 run needs the bridge, so 3 should come first.

## Risks

| Risk | Mitigation |
|---|---|
| CVM and BRAPI disagree at scale | PR 1a gates PR 5 before any dependency is built on the assumption |
| Silent wrong values for banks and insurers | An account number is trusted only when the line's own label agrees, so a bank's deposits are never read as debt nor its provisions as equity; the balance and continuity checks then refuse the write rather than log a warning |
| CVM's lag turns out no better than BRAPI's | PR 1b measures it against real filings before PR 5 is written · early evidence says the rebuild cadence, not the publication lag, is the constraint |
| A backfill is mistaken for a measurement | Lag counts only for filings that first appeared in a build later than the earliest recorded one; everything else is reported as backfill, and an empty sample prints "not enough observations yet" rather than a number |
| Ticker map rots as companies rename or list | Stored in DB, monthly unmapped-ticker report filtered to tickers with a market cap |
| A ticker is mapped to the wrong company | Every strategy declines on ambiguity; `Codigo_Negociacao` is validated against the B3 shape before use; `cvm_match_method` records the evidence so a disputed figure is traceable |
| CVM changes the archive layout | Real-filing fixtures in tests; the command fails loudly rather than writing nulls |
| Mixed-source series drift | `source` column plus no historical backfill · CVM writes only quarters BRAPI lacks |
