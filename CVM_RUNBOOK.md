# CVM Ingestion · Runbook

What to check, when, and what each answer means. Written after the pipeline shipped (see `CVM_INGESTION_PLAN.md`), while the reasoning is still fresh.

The first section is the one-off check that closes out the build. Everything after it is the routine.

---

## 1. The first rebuild · from Sunday 2026-08-16

Everything measured so far is **catch-up**: the pipeline was built after those filings were already published. No filing has yet been watched from receipt to live, so `filing to live` correctly reports nothing.

The Q2 deadline was **Friday 2026-08-14**. Around 70% of Brazilian issuers file in the final days, and the archive held only 196 of ~662 expected Q2 filings on 08-11. The rebuild that follows the deadline is the single most informative event of the year.

Run these from Sunday evening onward. Nothing is time-critical · the poll records everything automatically, and these commands only read.

### 1a. Did the archive rebuild at all?

```bash
curl -sI "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_2026.zip" \
  | grep -i last-modified
```

| Result | Meaning |
|---|---|
| A date **after** 2026-08-09 | Expected. Continue. |
| Still `Sun, 09 Aug 2026 10:39:17` | The weekly hypothesis is wrong, or CVM skipped a cycle. Do not conclude anything from one miss · check again the following Sunday before revising the plan. |

### 1b. What did our own poll record?

```bash
ssh root@poe.ma "cd /opt/sponda/backend && \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/sponda/venv/bin/python manage.py report_cvm_lag --year 2026"
```

Read it line by line:

| Line | Before Sunday | What to look for |
|---|---|---|
| `archive builds observed` | 1 | **2 or more.** This is the first cadence measurement. |
| `rebuild interval` | not enough observations | A number. **~7d confirms the weekly hypothesis.** |
| `filings recorded` | 859 (859 backfill) | Should jump by roughly 400–470 as Q2 lands. |
| `publication lag` | not enough observations | The first real figure · days from CVM receiving a filing to publishing it. |
| `CVM-sourced rows live` | 67 (67 not measurable) | The measurable count should become non-zero. |
| `filing to live` | not enough observations | **The number this whole effort exists to move.** |

### 1c. The decision rules

These were set before the data existed. Hold to them.

| Observation | Conclusion |
|---|---|
| `rebuild interval` ≈ 7d | Weekly confirmed. The plan's revised target (~3–4d median, 7d worst) stands. |
| `rebuild interval` ≈ 1d | Far better than assumed. Consider polling the sync more often than 4×/day. |
| `publication lag` median > 7d | **The plan's gate fails.** CVM buys little over BRAPI; reconsider whether PR 5 earns its keep. |
| `filing to live` median ≤ ~4d | The effort delivered. BRAPI's measured baseline was 7–21 days. |
| `filing to live` median > 7d | It did not. Find which hop is slow · compare `publication lag` against `filing to live`; the difference is ours. |

### 1d. Did the ingestion actually run?

```bash
ssh root@poe.ma "journalctl -u sponda-sync-cvm.service --since '3 days ago' --no-pager -o cat | tail -20"
```

Expect several hundred quarters written across the runs following the rebuild. Then confirm it settles:

```bash
ssh root@poe.ma "cd /opt/sponda/backend && \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/sponda/venv/bin/python manage.py sync_cvm_filings --year 2026 --dry-run | head -3"
```

Should end at `0 quarters to write · nothing downloaded`. If it keeps finding the same work every run, the idempotency rule has regressed · see §3.

### 1e. Spot-check the data itself

Pick two or three names that filed near the deadline and compare against the company's own release:

```bash
ssh root@poe.ma "cd /opt/sponda/backend && \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/sponda/venv/bin/python -c \"
import django; django.setup()
from quotes.models import QuarterlyEarnings, BalanceSheet
from datetime import date
for t in ['ITUB4','BBDC4','WEGE3']:
    e = QuarterlyEarnings.objects.filter(ticker=t, end_date=date(2026,6,30)).first()
    b = BalanceSheet.objects.filter(ticker=t, end_date=date(2026,6,30)).first()
    print(t, e.source if e else 'absent', e.net_income if e else None, b.stockholders_equity if b else None)
\""
```

A bank in that list is deliberate: equity must be the real figure, not *Provisões*, and `total_debt` must be **absent** rather than counting customer deposits.

### 1f. Record the answer

Add the measured figures to `CVM_INGESTION_PLAN.md` under *What PR 1b already established*, replacing the hypothesis language. The plan currently says "inferred from a single 2-day gap · a hypothesis, not a finding". After Sunday it is one or the other, and the document should say which.

---

## 2. The routine, once that is done

### Weekly, after each rebuild

```bash
ssh root@poe.ma "cd /opt/sponda/backend && \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/sponda/venv/bin/python manage.py report_cvm_lag --year 2026"
```

Watch `filing to live`. It is the regression signal · if the median drifts upward, something in the chain slowed, and comparing it against `publication lag` says whether the cause is CVM's or ours.

### Monthly, after `map_tickers_to_cvm` runs

Its output lists unmapped tickers **with a market cap**. A new name there is an IPO that will otherwise never be ingested. Resolve it:

```bash
python manage.py map_tickers_to_cvm --set NEWCO3=<cvm_code>
```

### Annually, February–March

`sync_cvm_fourth_quarters` runs daily and fills Q4 as DFPs arrive. Check in March that it wrote roughly the number of companies expected, and that refusals are the known pathological cases rather than something new.

---

## 3. Failure modes and what they mean

| Symptom | Likely cause | Where to look |
|---|---|---|
| Sync writes the same quarters every run | The idempotency rule regressed · `is_writable` should only permit a rewrite when a **later** filing exists | `quotes/cvm_writer.py::is_writable` |
| Sync writes nothing during a season | Ticker mapping empty, or precedence refusing everything | `map_tickers_to_cvm --dry-run`; check `Ticker.cvm_code` is populated |
| Many refusals from the continuity gate | Either a genuine wave of corporate events, or the gate is too tight | Each refusal names the ratio; verify against the filing before using `--force` |
| `filing to live` reports nothing after a rebuild | Every filing predates the observation window, or no rows were written | Compare `CVM-sourced rows live` against its "not measurable" count |
| A figure looks wrong on a page | Check `source` on the row first | `cvm` means we derived it; `brapi`/`fmp` means we did not |

### Using `--force`

The continuity gate refuses equity that moved an order of magnitude, because that is what reading the wrong line looks like. It cannot tell that from a merger. **Verify against the filing before overriding**, as was done for SAUD3 (Capital Social R$851m → R$14.90bn confirmed the Bradesco combination):

```bash
python manage.py seed_quarter_from_cvm --quarter 2026-06-30 --ticker XXXX3 --force
```

It logs a warning. The parser's own gates are not overridable.

---

## 4. Known gaps · deliberately open

These are documented rather than fixed. None is urgent; all are real.

| Gap | Detail |
|---|---|
| **WDCN3 unmappable** | Matches no company in CVM's registry. Will never ingest. Needs a human to identify the entity, then `--set`. |
| **AGXY3 permanently pending** | Lacks a usable annual, so the daily Q4 run downloads ~12 MB to skip it. Bounded. Suppressing it would miss a late DFP. |
| **A year disagreeing with its own quarters is undetectable** | AUAU3 and BOBR4 differ from theirs by 63% and 36%. From the annual and nine months alone this is indistinguishable from a bad quarter. Only visible against a Q4 from another source; `source` is what makes it auditable. |
| **A BDR sharing a ticker root** | `JBSS32` (BDR over JBS N.V.) would root-match to JBS S.A. None are currently in the universe. `cvm_match_method='root'` flags such rows. |
| **Q4 absorbs audit adjustments** | Deliberate · the four quarters then sum to the audited year, and BRAPI's series is never displaced. Measured: 277/279 derived Q4s matched BRAPI's own within 1%. |

---

## 5. What the numbers were, so drift is visible

Measured 2026-08-11/12, before any steady-state observation.

| Quantity | Value |
|---|---|
| Brazilian tickers mapped | 360 / 361 |
| Mapping methods | 340 published code, 5 root, 13 name, 2 manual |
| CVM vs BRAPI at n=347 (Q1 2026) | net income 0.34% differ, equity 0.33%, operating cash flow 1.03% |
| Filers parsed from the full archive | 416 / 416, none refused |
| Q4 2025 derived vs BRAPI's own | 277 / 279 within 1% |
| BRAPI tracking restatements | 9 / 9 |
| Restatement frequency | 30 of 827 documents (3.6%) |
| Archive publication lag within a build | ~2 days |
| Rebuild cadence | 3 consecutive days unchanged · consistent with weekly, unconfirmed |
