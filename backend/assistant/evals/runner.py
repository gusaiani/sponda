"""Case execution and scoring for the screening-agent eval harness.

Mirrors the /api/assistant/screen/ view's flow (assistant/views.py's
_screen_event_stream) without HTTP: classify_screening_question() gates the
request exactly like the view does, then run_screening_agent() drives the
same tool-calling loop the production endpoint drives. The only difference
is transport — events are consumed directly instead of being mapped onto
SSE frames.

Scoring compares what actually happened (a CaseObserved) against what the
dataset says should happen (Case.expected) and produces a ScoredCase with a
human-readable reason, so a failing case tells you why without re-running it
under a debugger.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Optional

from django.conf import settings
from django.test import override_settings

from assistant.agent import (
    AnswerToken,
    Completed,
    Failed,
    InterpretedFilters,
    ScreenResults,
    run_screening_agent,
)
from assistant.cost import calculate_cost
from assistant.guardrail import classify_screening_question
from assistant.history import build_history_messages

# Two floats compare equal when they differ by less than this — covers
# Decimal-vs-float noise from JSON round-tripping without letting a real
# threshold mismatch (e.g. 8 vs 8.1) slip through as a pass.
FLOAT_TOLERANCE = 1e-9

# render_report() and the CLI summary line only show the worst few
# failures, not a wall of text — five is generous enough to spot a pattern
# without dominating the report.
MAX_WORST_FAILURES = 5

# Languages the dataset uses double as run_screening_agent's locale
# parameter directly; anything else falls back to English, same default
# assistant.views.screen() uses for a missing/unknown locale.
_DEFAULT_LOCALE = "en"
_KNOWN_LOCALES = ("en", "pt")


# --- Case / dataset loading ---------------------------------------------


@dataclass
class Case:
    """One eval case, mirroring a line of screening_evals.jsonl.

    `expected` is kept as the raw dict rather than a further-typed
    sub-structure — its shape varies by `expected["kind"]` (screen/clarify/
    decline/refuse each use a different subset of keys), and scoring reads
    it directly rather than through an intermediate model.
    """

    id: str
    language: str
    category: str
    query: str
    expected: dict
    smoke: bool = False
    history: Optional[list] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Case":
        return cls(
            id=data["id"],
            language=data.get("language", "en"),
            category=data.get("category", ""),
            query=data["query"],
            expected=data["expected"],
            smoke=bool(data.get("smoke", False)),
            history=data.get("history"),
        )


def load_cases(path) -> list[Case]:
    """Parse screening_evals.jsonl into Case objects.

    One JSON object per line. Blank lines and lines starting with ``//``
    (used for the dataset's section headers and the scoring-canon comment
    block at the top of the file) are skipped rather than raising.
    """
    cases: list[Case] = []
    with open(path, "r", encoding="utf-8") as cases_file:
        for raw_line in cases_file:
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue
            cases.append(Case.from_dict(json.loads(line)))
    return cases


def filter_smoke_cases(cases: Iterable[Case]) -> list[Case]:
    """The subset tagged smoke:true — the fast, always-run CI sample."""
    return [case for case in cases if case.smoke]


def filter_cases_by_ids(cases: Iterable[Case], case_ids: Iterable[str]) -> list[Case]:
    """The subset whose id is in `case_ids` — for `--cases id,id` reruns."""
    wanted_ids = {case_id.strip() for case_id in case_ids if case_id.strip()}
    return [case for case in cases if case.id in wanted_ids]


def _locale_for_language(language: str) -> str:
    return language if language in _KNOWN_LOCALES else _DEFAULT_LOCALE


# --- Execution ------------------------------------------------------------


@dataclass
class CaseObserved:
    """What actually happened when a case was run.

    `arguments` is the last InterpretedFilters.arguments seen (the raw
    screen_companies tool-call payload: filters/countries/sectors/sort/
    limit) — kept as the full argument set, not just the filters sub-dict,
    since scoring needs countries/sectors/sort too. `kind` is the coarse
    outcome the scorer branches on: "refuse" (guardrail blocked it before
    the agent ever ran), "screen" (a screen_companies call was observed),
    or "no_screen" (the agent answered — clarify/decline — without one).
    """

    guardrail_classification: str
    kind: str  # "refuse" | "screen" | "no_screen"
    arguments: Optional[dict] = None
    tickers: list = field(default_factory=list)
    count: int = 0
    answer_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    failed_code: Optional[str] = None


@dataclass
class CaseResult:
    case: Case
    observed: CaseObserved
    latency_seconds: float
    cost_usd: Decimal


# A transient OpenAI failure should cost a retry, not a failed eval case —
# a case failure must mean the MODEL got it wrong. Rate limits get special
# treatment: a 429 means the tokens-per-minute window is exhausted, so a
# short retry is useless — the waits escalate past the window boundary.
# (The first full 76-case run failed 29 consecutive cases on sustained 429s
# under the old single-5s-retry policy; the second still lost every
# screen-heavy category with a 20+60s ladder, because the SDK's own inner
# retries kept re-saturating the window — the ladder has to escalate past
# several full windows, not one.) Persistent failures are recorded on the
# case (failed_code) instead of crashing the whole run.
RATE_LIMIT_RETRY_DELAYS = (20, 60, 120, 240)
TRANSIENT_RETRY_DELAY_SECONDS = 5

# Pause between cases so back-to-back multi-call cases don't burst straight
# into the rate-limit window that the retry policy then has to dig out of.
# 4s ≈ one screen case's token burst amortized across the minute window at
# tier-1 TPM; the full 76-case run stays under ~30 min even with pauses.
DEFAULT_PACING_SECONDS = 4.0


def _failed_case_result(case: Case, error: Exception, started_at: float) -> CaseResult:
    observed = CaseObserved(
        guardrail_classification="error",
        kind="no_screen",
        failed_code=f"exception:{type(error).__name__}",
    )
    return CaseResult(
        case=case,
        observed=observed,
        latency_seconds=time.monotonic() - started_at,
        cost_usd=Decimal("0"),
    )


def run_case(case: Case, model: str) -> CaseResult:
    """Run one case, retrying transient OpenAI failures before failing it.

    Rate limits (raised RateLimitError from the guardrail call, or the
    agent's own "rate_limited" Failed event) back off through every delay
    in RATE_LIMIT_RETRY_DELAYS. Any other APIError (timeouts included)
    gets one short retry. A case that still fails is recorded with
    failed_code = "exception:<Type>" rather than crashing the eval run.
    """
    import httpx
    from openai import APIError, RateLimitError

    started_at = time.monotonic()
    rate_limit_attempts = 0
    transient_retried = False
    while True:
        try:
            result = _attempt_case(case, model)
        except RateLimitError as error:
            if rate_limit_attempts < len(RATE_LIMIT_RETRY_DELAYS):
                time.sleep(RATE_LIMIT_RETRY_DELAYS[rate_limit_attempts])
                rate_limit_attempts += 1
                continue
            return _failed_case_result(case, error, started_at)
        except (APIError, httpx.HTTPError) as error:
            # Raw httpx errors escape the SDK's wrapping for guardrail calls
            # interrupted mid-request — same transient treatment as APIError.
            if not transient_retried:
                transient_retried = True
                time.sleep(TRANSIENT_RETRY_DELAY_SECONDS)
                continue
            return _failed_case_result(case, error, started_at)

        failed_code = result.observed.failed_code
        if failed_code == "rate_limited" and rate_limit_attempts < len(RATE_LIMIT_RETRY_DELAYS):
            time.sleep(RATE_LIMIT_RETRY_DELAYS[rate_limit_attempts])
            rate_limit_attempts += 1
            continue
        if failed_code == "upstream_timeout" and not transient_retried:
            transient_retried = True
            time.sleep(TRANSIENT_RETRY_DELAY_SECONDS)
            continue
        return result


def _attempt_case(case: Case, model: str) -> CaseResult:
    """One attempt at a case: the real guardrail + agent flow, no HTTP.

    Times the whole thing (guardrail call included, same as the view's
    started_at) for the latency percentiles, and prices the OpenAI usage
    via calculate_cost so the report can show a cost-per-case figure.
    """
    started_at = time.monotonic()

    history_messages = build_history_messages(
        case.history or [],
        max_turns=settings.ASSISTANT_MAX_HISTORY_TURNS,
        max_question_chars=settings.ASSISTANT_MAX_QUESTION_CHARS,
        max_answer_chars=settings.ASSISTANT_MAX_HISTORY_ANSWER_CHARS,
    )

    verdict = classify_screening_question(case.query, history_messages)

    arguments: Optional[dict] = None
    tickers: list = []
    count = 0
    answer_chunks: list[str] = []
    input_tokens = 0
    output_tokens = 0
    failed_code: Optional[str] = None
    kind = "refuse"

    if verdict.classification == "on_topic":
        kind = "no_screen"
        with override_settings(ASSISTANT_SCREENING_MODEL=model):
            for event in run_screening_agent(
                question=case.query,
                history_messages=history_messages,
                locale=_locale_for_language(case.language),
            ):
                if isinstance(event, InterpretedFilters):
                    # A refinement can restate the full filter set more
                    # than once across tool rounds — the LAST call is what
                    # actually ran, same rationale as the view's
                    # interpreted_filters tracking.
                    arguments = event.arguments
                    kind = "screen"
                elif isinstance(event, ScreenResults):
                    tickers = [row.get("ticker") for row in event.rows]
                    count = event.count
                elif isinstance(event, AnswerToken):
                    answer_chunks.append(event.text)
                elif isinstance(event, Completed):
                    input_tokens = event.input_tokens
                    output_tokens = event.output_tokens
                elif isinstance(event, Failed):
                    failed_code = event.code

    latency_seconds = time.monotonic() - started_at
    cost_usd = calculate_cost(model, input_tokens, output_tokens)

    observed = CaseObserved(
        guardrail_classification=verdict.classification,
        kind=kind,
        arguments=arguments,
        tickers=tickers,
        count=count,
        answer_text="".join(answer_chunks),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        failed_code=failed_code,
    )
    return CaseResult(
        case=case, observed=observed, latency_seconds=latency_seconds, cost_usd=cost_usd,
    )


# --- Scoring ---------------------------------------------------------------


@dataclass
class ScoredCase:
    case: Case
    observed: CaseObserved
    passed: bool
    reason: str


def _filters_equal(observed: Optional[dict], expected: Optional[dict]) -> bool:
    """Compare two {field: {min?, max?}} indicator-bound dicts.

    Bounds compare as floats within FLOAT_TOLERANCE so a Decimal from the
    model's JSON and a float/int literal in the dataset never mismatch on
    representation alone. Missing sides (None) are treated as `{}`.
    """
    observed = observed or {}
    expected = expected or {}
    if set(observed) != set(expected):
        return False
    for field_name in expected:
        observed_bounds = observed[field_name] or {}
        expected_bounds = expected[field_name] or {}
        if set(observed_bounds) != set(expected_bounds):
            return False
        for bound_key in expected_bounds:
            observed_value = observed_bounds[bound_key]
            expected_value = expected_bounds[bound_key]
            if observed_value is None or expected_value is None:
                if observed_value != expected_value:
                    return False
                continue
            if abs(float(observed_value) - float(expected_value)) > FLOAT_TOLERANCE:
                return False
    return True


def _match_filter_scope(observed_arguments: Optional[dict], expected: dict) -> tuple:
    """Compare an observed screen_companies argument set against an
    expected {filters|filters_any_of, countries?, sectors?, sort?} spec.

    `filters_any_of` (when the dataset marks a phrasing as honestly
    underdetermined, e.g. "single-digit PE10") holds alternative bare
    filters dicts — country/sector/sort expectations are shared across
    every variant, not repeated per-variant. Returns (matched, reason);
    reason is "" on a match.
    """
    arguments = observed_arguments or {}
    observed_filters = arguments.get("filters") or {}

    filter_variants = expected.get("filters_any_of")
    if filter_variants is not None:
        filters_ok = any(
            _filters_equal(observed_filters, variant) for variant in filter_variants
        )
        expected_repr = filter_variants
    else:
        filters_ok = _filters_equal(observed_filters, expected.get("filters"))
        expected_repr = expected.get("filters")
    if not filters_ok:
        return False, f"filters mismatch: observed={observed_filters!r}, expected={expected_repr!r}"

    observed_countries = set(arguments.get("countries") or [])
    expected_countries = set(expected.get("countries") or [])
    if observed_countries != expected_countries:
        return False, (
            f"countries mismatch: observed={sorted(observed_countries)}, "
            f"expected={sorted(expected_countries)}"
        )

    observed_sectors = set(arguments.get("sectors") or [])
    expected_sectors = set(expected.get("sectors") or [])
    if observed_sectors != expected_sectors:
        return False, (
            f"sectors mismatch: observed={sorted(observed_sectors)}, "
            f"expected={sorted(expected_sectors)}"
        )

    # Sort is only asserted when the case cares about it — most cases have
    # no opinion on row order, only on which rows qualify.
    expected_sort = expected.get("sort")
    if expected_sort is not None:
        observed_sort = arguments.get("sort")
        if observed_sort != expected_sort:
            return False, f"sort mismatch: observed={observed_sort!r}, expected={expected_sort!r}"

    return True, ""


def _score_screen(case: Case, observed: CaseObserved) -> tuple:
    if observed.kind != "screen":
        return False, "expected a screen_companies call but none was observed"

    expected = case.expected
    matched, reason = _match_filter_scope(observed.arguments, expected)
    if not matched:
        return False, reason

    subset = expected.get("expected_symbols_subset")
    if subset:
        missing = set(subset) - set(observed.tickers)
        if missing:
            return False, f"missing expected symbols: {sorted(missing)}"

    min_rows = expected.get("min_rows")
    if min_rows is not None and observed.count < min_rows:
        return False, f"expected >= {min_rows} rows, got {observed.count}"

    return True, ""


def _score_clarify(case: Case, observed: CaseObserved) -> tuple:
    if observed.kind == "screen":
        return False, "expected a clarifying question but a screen call was made"
    if "?" not in observed.answer_text:
        return False, "expected the answer to contain a clarifying question"
    return True, ""


def _score_decline(case: Case, observed: CaseObserved) -> tuple:
    expected = case.expected
    must_mention = expected.get("must_mention") or ""
    mentioned = (
        must_mention.lower() in observed.answer_text.lower() if must_mention else True
    )

    # A "partial decline" case (e.g. "PE10 under 10 and ROE above 15") asks
    # the model to screen on the supported half AND decline the rest —
    # expected.filters being present is the signal this is that shape.
    is_partial = expected.get("filters") is not None or expected.get("filters_any_of") is not None
    if is_partial:
        if observed.kind != "screen":
            return False, "expected a partial screen (decline) but no screen call was observed"
        matched, reason = _match_filter_scope(observed.arguments, expected)
        if not matched:
            return False, reason
        if not mentioned:
            return False, f"answer does not mention {must_mention!r}"
        return True, ""

    if observed.kind == "screen":
        return False, "expected a decline (no screen) but a screen call was made"
    if not mentioned:
        return False, f"answer does not mention {must_mention!r}"
    return True, ""


def _score_refuse(case: Case, observed: CaseObserved) -> tuple:
    if observed.kind == "refuse":
        return True, ""
    return (
        False,
        f"expected a refusal but the guardrail classified this as "
        f"{observed.guardrail_classification!r} and the agent ran",
    )


_SCORERS = {
    "screen": _score_screen,
    "clarify": _score_clarify,
    "decline": _score_decline,
    "refuse": _score_refuse,
}


def score_case(case: Case, observed: CaseObserved) -> ScoredCase:
    """Score one case's observed outcome against its expectation.

    Dispatches on `case.expected["kind"]`; an unknown kind is a hard
    dataset-authoring error, surfaced as a failing ScoredCase rather than
    an exception, so one malformed line doesn't crash the whole run.
    """
    kind = case.expected.get("kind")
    scorer = _SCORERS.get(kind)
    if scorer is None:
        return ScoredCase(
            case=case, observed=observed, passed=False,
            reason=f"unknown expected.kind {kind!r}",
        )
    passed, reason = scorer(case, observed)
    return ScoredCase(case=case, observed=observed, passed=passed, reason=reason)


# --- Aggregation ------------------------------------------------------------


@dataclass
class CategoryBreakdown:
    total: int
    passed: int

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total) if self.total else 0.0


@dataclass
class WorstFailure:
    case_id: str
    category: str
    language: str
    query: str
    expected: dict
    observed_arguments: Optional[dict]
    observed_answer: str
    reason: str
    # Diagnosis context: an empty answer with observed_kind="refuse" is a
    # guardrail misclassification, not an agent failure — without these two
    # fields the report can't distinguish them.
    guardrail_classification: str = ""
    failed_code: Optional[str] = None


@dataclass
class EvalRun:
    model: str
    total_cases: int
    passed_cases: int
    overall_pass_rate: float
    # None when the case subset run had no cases in that bucket (e.g. a
    # --cases rerun of only adversarial ids has no screen cases to score
    # filter-parse accuracy over).
    filter_parse_accuracy: Optional[float]
    refusal_rate: Optional[float]
    per_category: dict
    per_language: dict
    latency_p50_seconds: float
    latency_p95_seconds: float
    mean_cost_usd: Decimal
    total_cost_usd: Decimal
    worst_failures: list


def _percentile(values: list, percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(percentile * (len(ordered) - 1))))
    return ordered[index]


def _pass_rate(scored_cases: list) -> Optional[float]:
    if not scored_cases:
        return None
    return sum(1 for scored in scored_cases if scored.passed) / len(scored_cases)


def _breakdown_by(scored_cases: list, key) -> dict:
    grouped: dict = {}
    for scored in scored_cases:
        grouped.setdefault(key(scored), []).append(scored)
    return {
        name: CategoryBreakdown(
            total=len(items), passed=sum(1 for item in items if item.passed),
        )
        for name, items in grouped.items()
    }


def _select_worst_failures(scored_cases: list) -> list:
    """Up to MAX_WORST_FAILURES failures, screen-kind mismatches first.

    A screen-filter mismatch is almost always a prompt/tool-description
    bug worth fixing; a mis-scored clarify/decline/refuse is more often a
    borderline dataset judgment call. sorted() is stable, so within each
    bucket the original (dataset) order is preserved.
    """
    failures = [scored for scored in scored_cases if not scored.passed]
    ordered = sorted(
        failures, key=lambda scored: 0 if scored.case.expected.get("kind") == "screen" else 1,
    )
    return [
        WorstFailure(
            case_id=scored.case.id,
            category=scored.case.category,
            language=scored.case.language,
            query=scored.case.query,
            expected=scored.case.expected,
            observed_arguments=scored.observed.arguments,
            observed_answer=scored.observed.answer_text,
            reason=scored.reason,
            guardrail_classification=scored.observed.guardrail_classification,
            failed_code=scored.observed.failed_code,
        )
        for scored in ordered[:MAX_WORST_FAILURES]
    ]


def run_evals(
    cases: Iterable[Case], model: str, pacing_seconds: float = DEFAULT_PACING_SECONDS,
) -> EvalRun:
    """Run every case against `model` and return the aggregate EvalRun.

    Filter-parse accuracy is measured over every case whose
    expected.kind == "screen" — that covers plain/direction/geo/sort/
    refine cases AND the partial-unsupported cases (kind=decline with a
    filters spec is scored by _score_decline, not counted here; only true
    kind=screen cases count), matching the design doc's "non-adversarial
    filter-parse set". Refusal rate is measured over expected.kind ==
    "refuse" (the adversarial set).
    """
    cases = list(cases)
    scored_cases: list[ScoredCase] = []
    latencies: list[float] = []
    costs: list[Decimal] = []

    for case_index, case in enumerate(cases):
        if case_index and pacing_seconds:
            time.sleep(pacing_seconds)
        result = run_case(case, model)
        scored_cases.append(score_case(case, result.observed))
        latencies.append(result.latency_seconds)
        costs.append(result.cost_usd)

    total = len(scored_cases)
    passed = sum(1 for scored in scored_cases if scored.passed)

    screen_cases = [s for s in scored_cases if s.case.expected.get("kind") == "screen"]
    refuse_cases = [s for s in scored_cases if s.case.expected.get("kind") == "refuse"]

    total_cost = sum(costs, Decimal("0"))
    mean_cost = (total_cost / total) if total else Decimal("0")

    return EvalRun(
        model=model,
        total_cases=total,
        passed_cases=passed,
        overall_pass_rate=(passed / total) if total else 0.0,
        filter_parse_accuracy=_pass_rate(screen_cases),
        refusal_rate=_pass_rate(refuse_cases),
        per_category=_breakdown_by(scored_cases, key=lambda s: s.case.category),
        per_language=_breakdown_by(scored_cases, key=lambda s: s.case.language),
        latency_p50_seconds=_percentile(latencies, 0.50),
        latency_p95_seconds=_percentile(latencies, 0.95),
        mean_cost_usd=mean_cost,
        total_cost_usd=total_cost,
        worst_failures=_select_worst_failures(scored_cases),
    )
