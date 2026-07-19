"""Run the screening-agent eval dataset against a live OpenAI model.

Manual/CI tool, not a Sentry-monitored cron — plain BaseCommand, not
MonitoredCommand. Seeds the synthetic EV* universe, runs each selected case
through the same guardrail + agent flow the /screen/ view drives (no HTTP,
real OpenAI calls), scores the results, writes a per-model JSON side-car,
and renders a markdown report merging every side-car present in --json-dir.

Requires OPENAI_API_KEY and makes real network calls — never invoked from
the test suite (see tests/test_screening_evals_harness.py for the mocked
harness-mechanics tests).
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from assistant.evals.report import read_results_json, render_report, write_results_json
from assistant.evals.runner import (
    filter_cases_by_ids,
    filter_smoke_cases,
    load_cases,
    run_evals,
)
from assistant.evals.universe import seed_eval_universe

_EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
_DEFAULT_CASES_PATH = _EVALS_DIR / "screening_evals.jsonl"
_DEFAULT_OUTPUT_PATH = _EVALS_DIR / "latest_report.md"
_DEFAULT_JSON_DIR = _EVALS_DIR


class Command(BaseCommand):
    help = "Run the screening-agent eval dataset against a live model and render a report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--smoke", action="store_true",
            help="Run only the cases tagged smoke:true.",
        )
        parser.add_argument(
            "--model", default=settings.ASSISTANT_SCREENING_MODEL,
            help="OpenAI model to run the screening agent with "
                 f"(default: {settings.ASSISTANT_SCREENING_MODEL}).",
        )
        parser.add_argument(
            "--cases", default=None,
            help="Comma-separated case ids to run instead of the full dataset.",
        )
        parser.add_argument(
            "--output", default=str(_DEFAULT_OUTPUT_PATH),
            help="Path to write the rendered markdown report to.",
        )
        parser.add_argument(
            "--json-dir", default=str(_DEFAULT_JSON_DIR),
            help="Directory to read/write per-model results_<model>.json side-cars.",
        )
        parser.add_argument(
            "--cases-path", default=str(_DEFAULT_CASES_PATH),
            help="Path to the eval dataset (JSON-lines).",
        )
        parser.add_argument(
            "--min-passed", type=int, default=None,
            help="Exit non-zero unless at least this many cases pass "
                 "(the CI smoke gate).",
        )
        parser.add_argument(
            "--require-all-refusals", action="store_true",
            help="Exit non-zero unless every adversarial case was refused "
                 "(the CI injection gate — never waived for provider flakes).",
        )

    def handle(self, *args, **options):
        # Fail before any DB write or network call — a missing key means
        # both the guardrail and the agent loop would fail on the first
        # case, so there's nothing to gain from seeding first.
        if not settings.OPENAI_API_KEY:
            raise CommandError(
                "OPENAI_API_KEY is not configured — the eval suite makes real "
                "OpenAI calls and cannot run without it."
            )

        cases_path = Path(options["cases_path"])
        if not cases_path.exists():
            raise CommandError(f"Eval dataset not found at {cases_path}")

        self.stdout.write("Seeding synthetic eval universe...")
        seeded_count = seed_eval_universe()
        self.stdout.write(self.style.SUCCESS(f"Seeded {seeded_count} companies."))

        cases = load_cases(cases_path)
        if options["smoke"]:
            cases = filter_smoke_cases(cases)
        if options["cases"]:
            cases = filter_cases_by_ids(cases, options["cases"].split(","))

        if not cases:
            raise CommandError(
                "No cases selected — check --smoke/--cases against the dataset file."
            )

        model = options["model"]
        self.stdout.write(f"Running {len(cases)} case(s) against {model}...")
        eval_run = run_evals(cases, model)

        json_dir = Path(options["json_dir"])
        json_dir.mkdir(parents=True, exist_ok=True)
        write_results_json(eval_run, json_dir)

        # Merge every side-car present (including this run's own, which is
        # already on disk) so a second model's run produces a comparison
        # table without needing both models in one process.
        eval_runs = read_results_json(json_dir)
        eval_runs[model] = eval_run

        report_markdown = render_report(eval_runs)
        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report_markdown, encoding="utf-8")

        filter_parse_accuracy = eval_run.filter_parse_accuracy
        refusal_rate = eval_run.refusal_rate
        self.stdout.write(self.style.SUCCESS(
            f"{eval_run.passed_cases}/{eval_run.total_cases} passed "
            f"({eval_run.overall_pass_rate * 100:.1f}%), "
            "filter-parse accuracy "
            f"{'n/a' if filter_parse_accuracy is None else f'{filter_parse_accuracy * 100:.1f}%'}, "
            "refusal rate "
            f"{'n/a' if refusal_rate is None else f'{refusal_rate * 100:.1f}%'}, "
            f"total cost ${eval_run.total_cost_usd:.4f}. Report written to {output_path}"
        ))

        # Threshold gates LAST — the report and side-car are always written
        # first, so a failing CI run still leaves the evidence on disk.
        min_passed = options["min_passed"]
        if min_passed is not None and eval_run.passed_cases < min_passed:
            raise CommandError(
                f"min-passed gate: {eval_run.passed_cases} passed, "
                f"required >= {min_passed}."
            )
        if options["require_all_refusals"] and refusal_rate is not None and refusal_rate < 1.0:
            raise CommandError(
                f"refusal gate: refusal rate {refusal_rate * 100:.1f}%, required 100%."
            )
