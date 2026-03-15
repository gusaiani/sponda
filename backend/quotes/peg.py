"""PEG ratio (Peter Lynch) calculation logic — using PE10."""
from decimal import Decimal

from .cagr import compute_cagr
from .pe10 import get_annual_earnings, get_ipca_adjustment_factors


def calculate_peg(ticker: str, pe10: float | None) -> dict:
    """
    Calculate PEG ratio: PE10 ÷ earnings CAGR (%).

    Uses inflation-adjusted annual earnings to compute the CAGR.
    Falls back to log-linear regression when endpoint CAGR fails
    (e.g. negative earnings in the start/end year).

    Returns dict with:
        peg: float or None
        earningsCAGR: float or None (percentage, e.g. 15.0 = 15%)
        pegError: str or None
        earningsCAGRMethod: "endpoint" | "regression" | None
        earningsCAGRExcludedYears: list[int]
    """
    empty = {
        "peg": None,
        "earningsCAGR": None,
        "pegError": None,
        "earningsCAGRMethod": None,
        "earningsCAGRExcludedYears": [],
    }

    if pe10 is None:
        return {**empty, "pegError": "PE10 indisponível"}

    annual_data = get_annual_earnings(ticker)
    if len(annual_data) < 2:
        return {**empty, "pegError": "Dados insuficientes para calcular crescimento"}

    years = [d["year"] for d in annual_data]
    ipca_factors = get_ipca_adjustment_factors(years)

    # Build (year, adjusted_value) pairs for the CAGR calculator
    yearly_values = [
        (d["year"], float(d["net_income"] * ipca_factors.get(d["year"], Decimal("1"))))
        for d in annual_data
    ]

    cagr_result = compute_cagr(yearly_values)

    if cagr_result["cagr"] is None:
        error = cagr_result["error"]
        if cagr_result["excluded_years"]:
            excluded_str = ", ".join(str(y) for y in cagr_result["excluded_years"])
            error = f"{error} (anos excluídos: {excluded_str})"
        return {**empty, "pegError": error}

    cagr = cagr_result["cagr"]

    if cagr <= 0:
        return {
            **empty,
            "earningsCAGR": cagr,
            "earningsCAGRMethod": cagr_result["method"],
            "earningsCAGRExcludedYears": cagr_result["excluded_years"],
            "pegError": "PEG não aplicável — crescimento negativo",
        }

    peg = pe10 / cagr

    return {
        "peg": round(peg, 2),
        "earningsCAGR": cagr,
        "pegError": None,
        "earningsCAGRMethod": cagr_result["method"],
        "earningsCAGRExcludedYears": cagr_result["excluded_years"],
    }
