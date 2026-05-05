# Learning Mode

## Context

Sponda surfaces ~10 fundamental indicators per company (PE10, PFCF10, PEG, PFCF-PEG, D/E, D/E ex-lease, Liabilities/Equity, Current Ratio, Debt/Avg Earnings, Debt/Avg FCF). Newcomers to investing have no anchor to interpret these — is `debt/equity = 1.0` good or bad? Without context, the page is a wall of numbers.

**Goal.** A toggleable Learning Mode that, when ON, attaches a 5-tier color-coded rating to each indicator and an overall company grade (also 1–5, color-coded). Off by default; identical to today when off. Educational tooltips explain what each metric measures and why the rating landed where it did.

**Out of scope for this PR (open follow-up).** The exact thresholds, sector adjustments, and weights are placeholders. The plan delivers the infrastructure (data shape, backend pipeline, frontend components, toggle, i18n) so methodology can be tuned in a follow-up without re-plumbing.

## Decisions (confirmed)

- Ratings + overall grade computed **in Django**, persisted into `IndicatorSnapshot`, returned with existing API responses (no extra round-trips).
- Toggle lives in the **header** as a persistent pill next to `LanguageToggle`.
- **5-tier color scale** for both per-indicator ratings and overall company grade. No letters, no 0–100, no stars.
- Available to **everyone**: guests use `localStorage`, logged-in users use `/api/auth/preferences/`.

## Rating model

Five tiers, integers 1–5 (1=worst, 5=best), color-coded:

| Tier | Label key            | Color token              | Hex (light theme) |
|------|----------------------|--------------------------|-------------------|
| 1    | `learning.tier.1`    | `--color-rating-1`       | `#b91c1c` (red)    |
| 2    | `learning.tier.2`    | `--color-rating-2`       | `#ea580c` (orange) |
| 3    | `learning.tier.3`    | `--color-rating-3`       | `#a16207` (amber)  |
| 4    | `learning.tier.4`    | `--color-rating-4`       | `#65a30d` (lime)   |
| 5    | `learning.tier.5`    | `--color-rating-5`       | `#15803d` (green)  |

Translation labels are short and neutral: "Very weak / Weak / Average / Strong / Very strong". Tooltip copy elaborates with sector context.

**Overall company grade:** integer 1–5, computed as a weighted mean of available per-indicator ratings, rounded. If fewer than N indicators are available (config: default 4), the grade is `null` and we display "Not enough data" instead of a tier badge.

**Sector awareness.** Thresholds are defined per indicator with optional per-sector overrides. Backend lookup: `RATING_THRESHOLDS[indicator][sector] or RATING_THRESHOLDS[indicator]["__default__"]`. Initial commit ships only `__default__` thresholds; sector overrides are a follow-up data-only change.

## Architecture

### Backend (Django)

New module: **`backend/quotes/ratings.py`**
- `RATING_THRESHOLDS: dict[str, dict[str, list[float]]]` — per-indicator, per-sector tier boundaries (4 cuts → 5 tiers). Direction flag per indicator (lower-is-better for D/E, higher-is-better for current ratio in some interpretations — codified as `BETTER` enum).
- `INDICATOR_WEIGHTS: dict[str, float]` — overall-grade weights, normalized.
- `MIN_INDICATORS_FOR_GRADE = 4`.
- `rate_indicator(indicator: str, value: float | None, sector: str | None) -> int | None`
- `compute_overall_grade(ratings: dict[str, int | None]) -> int | None`
- All values are pure functions; no DB access.

Model change: **`backend/quotes/models.py`** — extend `IndicatorSnapshot`:
- New nullable `SmallIntegerField`s: `pe10_rating`, `pfcf10_rating`, `peg_rating`, `pfcf_peg_rating`, `debt_to_equity_rating`, `debt_ex_lease_to_equity_rating`, `liabilities_to_equity_rating`, `current_ratio_rating`, `debt_to_avg_earnings_rating`, `debt_to_avg_fcf_rating`, plus `overall_grade`.
- Migration auto-generated.

Refresh job: **`backend/quotes/management/commands/refresh_indicator_snapshots.py`** — call `rate_indicator` per field after each indicator value is computed, then `compute_overall_grade`. Save in the same transaction.

API:
- **`PE10View`** (`backend/quotes/views.py:653`) — extend response with a `ratings` block:
  ```json
  "ratings": {
    "pe10": 3, "pfcf10": null, "debtToEquity": 4, ...,
    "overall": 4,
    "methodologyVersion": "v1"
  }
  ```
  Computed inline if not snapshotted (e.g., for non-screener tickers); cached alongside existing PE10 cache.
- **`ScreenerView`** (`backend/quotes/views.py:1311`) — already reads `IndicatorSnapshot`; include the new rating fields in the serializer. (Filtering by grade is a follow-up; this PR exposes them for display only.)
- **No new endpoint** for the toggle preference: extend `/api/auth/preferences/` to accept `learning_mode_enabled: bool` (mirrors existing `allow_contact` pattern at `frontend/src/app/[locale]/account/page.tsx:454`).

Tests (TDD, pytest, **written first**):
- `backend/tests/test_ratings.py` — boundary cases per indicator, null handling, sector override fallthrough, weighted grade math, "not enough data" path, direction flag.
- `backend/tests/test_indicator_snapshot.py` (existing) — extend to assert ratings get populated on refresh.
- `backend/tests/test_pe10_view.py` — assert response includes `ratings` block when snapshot exists; computes on the fly when it doesn't.
- `backend/tests/test_auth_preferences.py` — accept and persist `learning_mode_enabled`.

### Frontend (Next.js + custom Context)

New context: **`frontend/src/learning/LearningModeContext.tsx`**
- Mirrors `LanguageContext` pattern: `useLearningMode()` hook returns `{ enabled, setEnabled }`.
- Persistence: `localStorage` key `sponda-learning-mode`; if `useAuth()` user is present, also PATCH `/api/auth/preferences/`. Initial value resolved from server-rendered user payload to avoid hydration flicker.
- Default: `false`.

New components:
- **`frontend/src/components/LearningModeToggle.tsx`** — pill in header, shown next to `LanguageToggle` inside `AuthHeader.tsx` (desktop + mobile menu). Icon + short label (`t("learning.toggle.label")`). One-click toggle, no dropdown.
- **`frontend/src/components/RatingChip.tsx`** — small colored chip rendering a 1–5 dot/bar plus tier label. Props: `{ rating: 1|2|3|4|5|null, indicator: string, value: number|null }`. Renders nothing when learning mode is OFF or rating is null. Tooltip on hover/focus shows: indicator name, what it measures, tier label, sector context note.
- **`frontend/src/components/CompanyGradeCard.tsx`** — top-of-page card on company home showing the overall 1–5 grade, color block, short rationale ("3 strong indicators, 1 weak"). Hidden when learning mode is OFF.
- **`frontend/src/components/IndicatorTooltip.tsx`** — reusable tooltip wrapper extending the existing CSS-only tooltip pattern in `auth-header.css:80-134`. No new dependency.

Component edits (additive — no behavior change when learning mode is off):
- **`frontend/src/components/CompanyMetricsCard.tsx`** — render `<RatingChip>` next to each metric. Add `<CompanyGradeCard>` at the top of the metrics tab.
- **`frontend/src/components/CompareTab.tsx`** — render `<RatingChip>` per indicator cell.
- **`frontend/src/app/[locale]/screener/page.tsx`** — show `<RatingChip>` per cell + a Grade column.
- **`frontend/src/components/HomepageCompanyCards.tsx`**, **`PopularCompanies.tsx`**, **`SavedLists.tsx`** — show overall grade chip per row.
- **Charts tab, Fundamentals tab** — left untouched (raw historical data, not point-in-time indicators).

Hook updates:
- **`frontend/src/hooks/usePE10.ts`** — extend `QuoteResult` type to include `ratings` block. No fetch logic changes; ratings ride the existing payload.

Styling:
- **`frontend/src/styles/global.css:11`** — add `--color-rating-1..5` tokens (light + dark themes).
- **`frontend/src/styles/rating-chip.css`** — chip layout, dot, tooltip transitions. **All sizes in px** per project rule.

i18n:
- **`frontend/src/i18n/types.ts`** — add `learning.*` keys to `TranslationDictionary`: toggle label/title, 5 tier names, per-indicator `name`/`what_it_measures`/`why_it_varies`/`good_means`/`bad_means`, grade card copy, "not enough data" copy.
- **All 7 locale files** — add the keys. Portuguese first (primary user base), then translate the rest. Keep copy short and factual per global writing-style preferences.

Tests (TDD, vitest, **written first**):
- `frontend/src/learning/LearningModeContext.test.tsx` — toggle on/off, localStorage persistence, server-side persistence when authed, hydration without flicker.
- `frontend/src/components/RatingChip.test.tsx` — renders nothing when off, renders correct color/label per tier, null handling, tooltip content.
- `frontend/src/components/CompanyGradeCard.test.tsx` — overall grade rendering, "not enough data" path.
- `frontend/src/components/LearningModeToggle.test.tsx` — click toggles state.

E2E (Playwright):
- `frontend/e2e/learning-mode.spec.ts` — toggle in header turns chips/grade on across company page; persists across reload (localStorage); persists across login.

## UX details

- **Toggle visual**: pill with a small graduation cap or "1·2·3" icon, label "Learn"/"Aprender" etc. Active state uses `--color-accent`. Inactive uses neutral border.
- **First-time popover**: when a user toggles ON for the first time, a one-time tooltip on the toggle explains what's now visible ("Each indicator gets a 1–5 rating; hover for details."). Dismissed forever via `localStorage` key `sponda-learning-mode-introduced`.
- **Chip placement**: trailing the metric value, not replacing it. Numbers stay primary; ratings are decoration.
- **Tooltip content**: 3 short paragraphs — what the metric measures, what this value usually implies, why the threshold may differ by sector. Educational, not prescriptive. Closes with "Methodology v1 — sector-aware refinements coming."
- **Color accessibility**: include shape/numeral inside chip (not color-only) so it works with color-blindness and grayscale.
- **Mobile**: chip shrinks to a colored dot + numeral; tap opens tooltip as a bottom sheet (reuse existing mobile menu pattern).

## Performance

- Ratings precomputed in `IndicatorSnapshot` daily — **zero added cost** for screener and homepage cards.
- For the company page, ratings are computed once per `PE10View` request and cached alongside the existing PE10 cache (`pe10:{TICKER}`, 24h TTL). No new network fetches from the frontend.
- Toggle is a render-only concern: chip components return `null` when disabled. No reflow risk because reserved space is small and only appears when ON.
- i18n bundle grows by per-indicator copy × 7 locales. Mitigation: keep copy short; if bundle becomes a concern in profiling, lazy-load `learning.*` translations by route.

## Critical files

| Concern                          | Path                                                               |
|----------------------------------|--------------------------------------------------------------------|
| Rating thresholds + math         | `backend/quotes/ratings.py` (new)                                  |
| Snapshot model                   | `backend/quotes/models.py` (IndicatorSnapshot, ~line 237)          |
| Snapshot refresh                 | `backend/quotes/management/commands/refresh_indicator_snapshots.py` |
| Company API response             | `backend/quotes/views.py:653` (PE10View)                            |
| Screener API response            | `backend/quotes/views.py:1311` (ScreenerView)                       |
| User preference                  | `/api/auth/preferences/` handler (existing)                         |
| Frontend type                    | `frontend/src/hooks/usePE10.ts:33` (QuoteResult)                    |
| Learning mode context            | `frontend/src/learning/LearningModeContext.tsx` (new)               |
| Header toggle                    | `frontend/src/components/AuthHeader.tsx`                            |
| Rating chip                      | `frontend/src/components/RatingChip.tsx` (new)                      |
| Company grade card               | `frontend/src/components/CompanyGradeCard.tsx` (new)                |
| Company page integration         | `frontend/src/components/CompanyMetricsCard.tsx`                    |
| Compare tab                      | `frontend/src/components/CompareTab.tsx`                            |
| Screener page                    | `frontend/src/app/[locale]/screener/page.tsx`                       |
| Color tokens                     | `frontend/src/styles/global.css:11`                                 |
| Translation types                | `frontend/src/i18n/types.ts`                                        |
| Translation files                | `frontend/src/i18n/locales/{pt,en,es,zh,fr,de,it}.ts`               |

## Implementation order

1. **Backend ratings module + tests** (pure functions, no model change yet).
2. **Migration + IndicatorSnapshot extension + refresh job + tests.**
3. **Extend `PE10View` + `ScreenerView` responses + tests.**
4. **Extend `/api/auth/preferences/` to accept `learning_mode_enabled` + tests.**
5. **Frontend `LearningModeContext` + tests.**
6. **`RatingChip`, `IndicatorTooltip`, `CompanyGradeCard`, `LearningModeToggle` + tests.**
7. **Integrate into `CompanyMetricsCard`, `CompareTab`, `screener/page.tsx`, homepage cards, saved lists.**
8. **i18n: types + 7 locales (pt first, then en, then the rest).**
9. **Color tokens + chip CSS.**
10. **Playwright E2E.**
11. **README update** (per global preferences): what the feature does, how it works, methodology version note, env vars (none new), local-testing steps.

Each step is its own commit; the feature lands as a single PR.

## Verification

- `cd backend && pytest backend/tests/test_ratings.py backend/tests/test_indicator_snapshot.py backend/tests/test_pe10_view.py backend/tests/test_auth_preferences.py` — all green.
- `cd frontend && rtk vitest run` — all green.
- `cd frontend && rtk playwright test learning-mode` — green.
- `cd frontend && rtk next build` — clean build, no type errors.
- Manual: load `/<locale>/<ticker>` for a US ticker (e.g. AAPL) and a BR ticker (e.g. PETR4) — toggle Learning Mode in header, confirm chips + grade appear, hover one indicator and read the tooltip, reload page and confirm state persists, log in/out and confirm persistence per-mode (server vs localStorage), check screener has Grade column, check mobile layout, check all 7 locales render the toggle label.
- Run `rtk python manage.py refresh_indicator_snapshots` and confirm rating columns populate.

## Follow-ups (out of scope here)

- Real, sector-aware threshold values (data-only PR once methodology is agreed).
- Filter screener by overall grade.
- Per-indicator deep-dive page under `/[locale]/learn/<indicator>` reusing `PE10Explainer` patterns.
- Surface methodology version + a "How we grade" link in the tooltip footer pointing to a public doc.
- Telemetry: count toggle activations to learn how many users engage with it.
