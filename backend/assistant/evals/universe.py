"""Synthetic fixture universe for the screening eval harness.

The dataset in ``screening_evals.jsonl`` expects deterministic answers, so
the companies it screens against can never be the real, ever-changing
production universe. This module is the single source of truth for that
fixture universe: 14 "EV"-prefixed synthetic companies with hand-picked
indicator values, spanning boundary cases (e.g. a PE10 exactly at a
threshold used by the dataset) on both sides of every filter the dataset
exercises.

``seed_eval_universe()`` is idempotent — safe to call at the top of every
``run_screening_evals`` invocation — so re-running the command never
duplicates rows or drifts from this table.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from quotes.models import IndicatorSnapshot, Ticker

# Every indicator field EVAL_UNIVERSE carries, in the same order
# IndicatorSnapshot.INDICATOR_FIELDS lists them (minus market_cap, which is
# handled separately since it also lives on Ticker).
_INDICATOR_FIELDS = (
    "pe10",
    "pfcf10",
    "peg",
    "pfcf_peg",
    "debt_to_equity",
    "debt_ex_lease_to_equity",
    "liabilities_to_equity",
    "current_ratio",
    "debt_to_avg_earnings",
    "debt_to_avg_fcf",
)

# The three EVUSA giants carry quadrillion-scale market caps — far above any
# real company — so "largest in the database" cases (sort=-market_cap top-N)
# stay deterministic even when the universe is seeded into a shared local dev
# DB alongside real tickers, not just into CI's clean database.
#
# The 14 synthetic companies the eval dataset screens against. Values are
# hand-picked so every dataset case has one deterministic, human-verified
# answer — see the design doc for the boundary rationale per company.
EVAL_UNIVERSE: tuple[dict, ...] = (
    {
        "symbol": "EVBRA1", "name": "Petro Eval", "sector": "Energy", "country": "BR",
        "market_cap": 80_000_000_000,
        "pe10": 4.5, "pfcf10": 3.8, "peg": 0.5, "pfcf_peg": 0.4,
        "debt_to_equity": 0.8, "debt_ex_lease_to_equity": 0.7,
        "liabilities_to_equity": 1.5, "current_ratio": 1.8,
        "debt_to_avg_earnings": 2.0, "debt_to_avg_fcf": 1.2,
        "current_price": 32.5,
    },
    {
        "symbol": "EVBRA2", "name": "Minerio Eval", "sector": "Basic Materials", "country": "BR",
        "market_cap": 60_000_000_000,
        "pe10": 7.9, "pfcf10": 6.5, "peg": 0.9, "pfcf_peg": 0.8,
        "debt_to_equity": 0.5, "debt_ex_lease_to_equity": 0.5,
        "liabilities_to_equity": 1.1, "current_ratio": 2.1,
        "debt_to_avg_earnings": 1.9, "debt_to_avg_fcf": 2.8,
        "current_price": 61.2,
    },
    {
        "symbol": "EVBRA3", "name": "Fabrica Eval", "sector": "Industrials", "country": "BR",
        "market_cap": 10_000_000_000,
        "pe10": 8.4, "pfcf10": 9.0, "peg": 1.4, "pfcf_peg": 1.5,
        "debt_to_equity": 1.0, "debt_ex_lease_to_equity": 0.9,
        "liabilities_to_equity": 2.0, "current_ratio": 1.0,
        "debt_to_avg_earnings": 3.5, "debt_to_avg_fcf": 3.0,
        "current_price": 18.4,
    },
    {
        "symbol": "EVBRA4", "name": "Luz Eval", "sector": "Utilities", "country": "BR",
        "market_cap": 20_000_000_000,
        "pe10": 15.0, "pfcf10": 11.0, "peg": 1.8, "pfcf_peg": 1.6,
        "debt_to_equity": 1.9, "debt_ex_lease_to_equity": 1.7,
        "liabilities_to_equity": 2.8, "current_ratio": 0.9,
        "debt_to_avg_earnings": 6.0, "debt_to_avg_fcf": 5.5,
        "current_price": 44.0,
    },
    {
        "symbol": "EVBRA5", "name": "Nova Eval", "sector": "Technology", "country": "BR",
        "market_cap": 5_000_000_000,
        "pe10": None, "pfcf10": None, "peg": None, "pfcf_peg": None,
        "debt_to_equity": 0.2, "debt_ex_lease_to_equity": 0.2,
        "liabilities_to_equity": 0.4, "current_ratio": 2.9,
        "debt_to_avg_earnings": None, "debt_to_avg_fcf": None,
        "current_price": 12.0,
    },
    {
        "symbol": "EVUSA1", "name": "Cheap Tech", "sector": "Technology", "country": "US",
        "market_cap": 8_000_000_000_000_000,
        "pe10": 6.0, "pfcf10": 5.5, "peg": 0.6, "pfcf_peg": 0.6,
        "debt_to_equity": 0.1, "debt_ex_lease_to_equity": 0.1,
        "liabilities_to_equity": 0.5, "current_ratio": 3.2,
        "debt_to_avg_earnings": 0.4, "debt_to_avg_fcf": 0.5,
        "current_price": 140,
    },
    {
        "symbol": "EVUSA2", "name": "Mega Growth", "sector": "Technology", "country": "US",
        "market_cap": 9_000_000_000_000_000,
        "pe10": 32.0, "pfcf10": 28.0, "peg": 2.5, "pfcf_peg": 2.3,
        "debt_to_equity": 0.3, "debt_ex_lease_to_equity": 0.3,
        "liabilities_to_equity": 0.8, "current_ratio": 2.0,
        "debt_to_avg_earnings": 1.0, "debt_to_avg_fcf": 1.1,
        "current_price": 310,
    },
    {
        "symbol": "EVUSA3", "name": "Old Bank", "sector": "Financial Services", "country": "US",
        "market_cap": 7_000_000_000_000_000,
        "pe10": 9.5, "pfcf10": 8.8, "peg": 1.1, "pfcf_peg": 1.0,
        "debt_to_equity": 2.5, "debt_ex_lease_to_equity": 2.5,
        "liabilities_to_equity": 8.0, "current_ratio": None,
        "debt_to_avg_earnings": 4.0, "debt_to_avg_fcf": 4.2,
        "current_price": 55,
    },
    {
        "symbol": "EVUSA4", "name": "Rust Industrial", "sector": "Industrials", "country": "US",
        "market_cap": 8_000_000_000,
        "pe10": 11.0, "pfcf10": 12.5, "peg": 1.6, "pfcf_peg": 1.9,
        "debt_to_equity": 1.5, "debt_ex_lease_to_equity": 1.3,
        "liabilities_to_equity": 2.6, "current_ratio": 0.6,
        "debt_to_avg_earnings": 5.0, "debt_to_avg_fcf": 6.0,
        "current_price": 23,
    },
    {
        "symbol": "EVUSA5", "name": "Micro Value", "sector": "Industrials", "country": "US",
        "market_cap": 300_000_000,
        "pe10": 3.2, "pfcf10": 2.9, "peg": 0.4, "pfcf_peg": 0.3,
        "debt_to_equity": 0.4, "debt_ex_lease_to_equity": 0.4,
        "liabilities_to_equity": 0.9, "current_ratio": 2.5,
        "debt_to_avg_earnings": 0.6, "debt_to_avg_fcf": 0.5,
        "current_price": 8.1,
    },
    {
        "symbol": "EVUSA6", "name": "Util US", "sector": "Utilities", "country": "US",
        "market_cap": 45_000_000_000,
        "pe10": 13.0, "pfcf10": 9.5, "peg": 1.5, "pfcf_peg": 1.2,
        "debt_to_equity": 1.2, "debt_ex_lease_to_equity": 1.1,
        "liabilities_to_equity": 2.2, "current_ratio": 1.1,
        "debt_to_avg_earnings": 4.5, "debt_to_avg_fcf": 3.8,
        "current_price": 71,
    },
    {
        "symbol": "EVDEU1", "name": "Werk Eval", "sector": "Industrials", "country": "DE",
        "market_cap": 30_000_000_000,
        "pe10": 7.2, "pfcf10": 6.8, "peg": 0.8, "pfcf_peg": 0.8,
        "debt_to_equity": 0.9, "debt_ex_lease_to_equity": 0.8,
        "liabilities_to_equity": 1.7, "current_ratio": 1.6,
        "debt_to_avg_earnings": 2.2, "debt_to_avg_fcf": 2.5,
        "current_price": 88,
    },
    {
        "symbol": "EVDEU2", "name": "Strom Eval", "sector": "Utilities", "country": "DE",
        "market_cap": 25_000_000_000,
        "pe10": 9.8, "pfcf10": 7.4, "peg": 1.2, "pfcf_peg": 1.0,
        "debt_to_equity": 1.4, "debt_ex_lease_to_equity": 1.2,
        "liabilities_to_equity": 2.4, "current_ratio": 1.1,
        "debt_to_avg_earnings": 3.1, "debt_to_avg_fcf": 2.9,
        "current_price": 34,
    },
    {
        "symbol": "EVDEU3", "name": "Auto Eval", "sector": "Industrials", "country": "DE",
        "market_cap": 70_000_000_000,
        "pe10": 5.5, "pfcf10": None, "peg": 0.7, "pfcf_peg": None,
        "debt_to_equity": 1.1, "debt_ex_lease_to_equity": 0.9,
        "liabilities_to_equity": 2.1, "current_ratio": 1.3,
        "debt_to_avg_earnings": 2.6, "debt_to_avg_fcf": 3.4,
        "current_price": 62,
    },
)


def _to_decimal(value: Optional[float]) -> Optional[Decimal]:
    """Convert a plain float/int from EVAL_UNIVERSE into a Decimal for the
    DecimalField columns, preserving None (missing-value probes)."""
    return None if value is None else Decimal(str(value))


def seed_eval_universe() -> int:
    """Idempotently seed the synthetic EV* eval universe.

    ``update_or_create`` per company, keyed on symbol/ticker, so re-running
    this at the top of every eval command invocation never creates
    duplicates or leaves stale rows behind. Returns the number of companies
    seeded, for the command's log line.
    """
    for company in EVAL_UNIVERSE:
        Ticker.objects.update_or_create(
            symbol=company["symbol"],
            defaults={
                "name": company["name"],
                "display_name": company["name"],
                "sector": company["sector"],
                "country": company["country"],
                "type": "stock",
                "market_cap": company["market_cap"],
            },
        )
        IndicatorSnapshot.objects.update_or_create(
            ticker=company["symbol"],
            defaults={
                # Mirrors Ticker.market_cap — the screener reads market_cap
                # off the snapshot, never off Ticker directly.
                "market_cap": company["market_cap"],
                "current_price": _to_decimal(company["current_price"]),
                **{
                    field: _to_decimal(company[field])
                    for field in _INDICATOR_FIELDS
                },
            },
        )
    return len(EVAL_UNIVERSE)
