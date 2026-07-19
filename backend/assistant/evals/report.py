"""Markdown report rendering and JSON side-car persistence for eval runs.

Each `manage.py run_screening_evals` invocation covers one model. To get a
model-comparison table without running two models in the same process, each
invocation writes its EvalRun to `results_<model>.json` in the json-dir, and
`render_report` is handed whatever `read_results_json` finds there — so a
gpt-4o run followed by a gpt-4o-mini run (each its own command invocation)
merges into one comparison table on the second run.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .runner import CategoryBreakdown, EvalRun, WorstFailure

RESULTS_FILENAME_TEMPLATE = "results_{model}.json"


# --- JSON side-car persistence ---------------------------------------------


def _breakdown_to_dict(breakdown: dict) -> dict:
    return {
        name: {"total": item.total, "passed": item.passed}
        for name, item in breakdown.items()
    }


def _breakdown_from_dict(data: dict) -> dict:
    return {
        name: CategoryBreakdown(total=item["total"], passed=item["passed"])
        for name, item in data.items()
    }


def _eval_run_to_dict(eval_run: EvalRun) -> dict:
    return {
        "model": eval_run.model,
        "total_cases": eval_run.total_cases,
        "passed_cases": eval_run.passed_cases,
        "overall_pass_rate": eval_run.overall_pass_rate,
        "filter_parse_accuracy": eval_run.filter_parse_accuracy,
        "refusal_rate": eval_run.refusal_rate,
        "per_category": _breakdown_to_dict(eval_run.per_category),
        "per_language": _breakdown_to_dict(eval_run.per_language),
        "latency_p50_seconds": eval_run.latency_p50_seconds,
        "latency_p95_seconds": eval_run.latency_p95_seconds,
        "mean_cost_usd": str(eval_run.mean_cost_usd),
        "total_cost_usd": str(eval_run.total_cost_usd),
        "worst_failures": [
            {
                "case_id": failure.case_id,
                "category": failure.category,
                "language": failure.language,
                "query": failure.query,
                "expected": failure.expected,
                "observed_arguments": failure.observed_arguments,
                "observed_answer": failure.observed_answer,
                "reason": failure.reason,
                "guardrail_classification": failure.guardrail_classification,
                "failed_code": failure.failed_code,
            }
            for failure in eval_run.worst_failures
        ],
    }


def _eval_run_from_dict(data: dict) -> EvalRun:
    return EvalRun(
        model=data["model"],
        total_cases=data["total_cases"],
        passed_cases=data["passed_cases"],
        overall_pass_rate=data["overall_pass_rate"],
        filter_parse_accuracy=data["filter_parse_accuracy"],
        refusal_rate=data["refusal_rate"],
        per_category=_breakdown_from_dict(data["per_category"]),
        per_language=_breakdown_from_dict(data["per_language"]),
        latency_p50_seconds=data["latency_p50_seconds"],
        latency_p95_seconds=data["latency_p95_seconds"],
        mean_cost_usd=Decimal(data["mean_cost_usd"]),
        total_cost_usd=Decimal(data["total_cost_usd"]),
        worst_failures=[WorstFailure(**failure) for failure in data["worst_failures"]],
    )


def write_results_json(eval_run: EvalRun, json_dir) -> Path:
    """Write one model's EvalRun to results_<model>.json in `json_dir`."""
    path = Path(json_dir) / RESULTS_FILENAME_TEMPLATE.format(model=eval_run.model)
    path.write_text(
        json.dumps(_eval_run_to_dict(eval_run), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def read_results_json(json_dir) -> dict:
    """Load every results_<model>.json present in `json_dir`.

    Returns {model_name: EvalRun}, sorted by filename so report ordering is
    stable across runs regardless of filesystem iteration order.
    """
    eval_runs: dict = {}
    for path in sorted(Path(json_dir).glob(RESULTS_FILENAME_TEMPLATE.format(model="*"))):
        data = json.loads(path.read_text(encoding="utf-8"))
        eval_runs[data["model"]] = _eval_run_from_dict(data)
    return eval_runs


# --- Markdown rendering ------------------------------------------------


def _format_percent(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _format_usd(value: Decimal) -> str:
    return f"${value:.4f}"


def _overall_table(eval_runs: dict) -> list:
    header = (
        "| Model | Cases | Pass Rate | Filter-Parse Accuracy | Refusal Rate | "
        "p50 Latency (s) | p95 Latency (s) | Mean Cost (USD) | Total Cost (USD) |"
    )
    separator = "|---|---|---|---|---|---|---|---|---|"
    rows = [header, separator]
    for model, eval_run in eval_runs.items():
        rows.append(
            f"| {model} | {eval_run.total_cases} | "
            f"{_format_percent(eval_run.overall_pass_rate)} | "
            f"{_format_percent(eval_run.filter_parse_accuracy)} | "
            f"{_format_percent(eval_run.refusal_rate)} | "
            f"{eval_run.latency_p50_seconds:.2f} | {eval_run.latency_p95_seconds:.2f} | "
            f"{_format_usd(eval_run.mean_cost_usd)} | {_format_usd(eval_run.total_cost_usd)} |"
        )
    return rows


def _comparison_table(eval_runs: dict) -> list:
    models = list(eval_runs)
    header = "| Metric | " + " | ".join(models) + " |"
    separator = "|---" * (len(models) + 1) + "|"
    rows = [header, separator]
    metric_rows = (
        ("Pass Rate", lambda run: _format_percent(run.overall_pass_rate)),
        ("Filter-Parse Accuracy", lambda run: _format_percent(run.filter_parse_accuracy)),
        ("Refusal Rate", lambda run: _format_percent(run.refusal_rate)),
        ("Mean Cost (USD)", lambda run: _format_usd(run.mean_cost_usd)),
        ("Total Cost (USD)", lambda run: _format_usd(run.total_cost_usd)),
    )
    for label, render in metric_rows:
        values = " | ".join(render(eval_runs[model]) for model in models)
        rows.append(f"| {label} | {values} |")
    return rows


def _breakdown_table(breakdown: dict) -> list:
    if not breakdown:
        return ["_no cases_"]
    rows = ["| Name | Passed | Total | Pass Rate |", "|---|---|---|---|"]
    for name in sorted(breakdown):
        item = breakdown[name]
        rows.append(f"| {name} | {item.passed} | {item.total} | {_format_percent(item.pass_rate)} |")
    return rows


def _worst_failures_section(worst_failures: list) -> list:
    if not worst_failures:
        return ["_no failures_"]
    lines: list = []
    for index, failure in enumerate(worst_failures, start=1):
        lines += [
            f"**{index}. `{failure.case_id}`** ({failure.category}/{failure.language})",
            "",
            f"- Query: {failure.query}",
            f"- Expected: `{json.dumps(failure.expected, ensure_ascii=False)}`",
            f"- Observed arguments: `{json.dumps(failure.observed_arguments, ensure_ascii=False)}`",
            f"- Observed answer: {failure.observed_answer!r}",
            f"- Guardrail: {failure.guardrail_classification or 'n/a'}"
            + (f" · failed: {failure.failed_code}" if failure.failed_code else ""),
            f"- Reason: {failure.reason}",
            "",
        ]
    return lines


def render_report(eval_runs: dict, iteration_notes: Optional[str] = None) -> str:
    """Render the full markdown report for one or more model runs.

    `eval_runs` is {model_name: EvalRun}. A model-comparison section is
    only added when more than one model is present — a single-model report
    has nothing to compare against.
    """
    lines: list = ["# Screening Eval Report", ""]

    if iteration_notes:
        lines += ["## Iteration Notes", "", iteration_notes.strip(), ""]

    lines += ["## Overall", ""]
    lines += _overall_table(eval_runs)
    lines.append("")

    if len(eval_runs) > 1:
        lines += ["## Model Comparison", ""]
        lines += _comparison_table(eval_runs)
        lines.append("")

    for model, eval_run in eval_runs.items():
        lines += [f"## {model}", ""]
        lines += ["### Per-Category", ""]
        lines += _breakdown_table(eval_run.per_category)
        lines.append("")
        lines += ["### Per-Language", ""]
        lines += _breakdown_table(eval_run.per_language)
        lines.append("")
        lines += ["### Worst Failures", ""]
        lines += _worst_failures_section(eval_run.worst_failures)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
