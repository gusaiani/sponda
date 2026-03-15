"""PFCLG (Price/FCF-to-Growth) ratio — Peter Lynch PEG applied to free cash flow."""
from decimal import Decimal

from .cagr import compute_cagr
from .pe10 import get_ipca_adjustment_factors
from .pfcf10 import get_annual_fcf


def calculate_pfcf_peg(ticker: str, pfcf10: float | None) -> dict:
    """
    Calculate PFCLG ratio: PFCF10 ÷ FCF CAGR (%).

    Uses inflation-adjusted annual FCF to compute the CAGR.
    Falls back to log-linear regression when endpoint CAGR fails.

    Returns dict with:
        pfcfPeg: float or None
        fcfCAGR: float or None (percentage, e.g. 15.0 = 15%)
        pfcfPegError: str or None
        fcfCAGRMethod: "endpoint" | "regression" | None
        fcfCAGRExcludedYears: list[int]
    """
    empty = {
        "pfcfPeg": None,
        "fcfCAGR": None,
        "pfcfPegError": None,
        "fcfCAGRMethod": None,
        "fcfCAGRExcludedYears": [],
    }

    if pfcf10 is None:
        return {**empty, "pfcfPegError": "PFCF10 indisponível"}

    annual_data = get_annual_fcf(ticker)
    if len(annual_data) < 2:
        return {**empty, "pfcfPegError": "Dados insuficientes para calcular crescimento"}

    years = [d["year"] for d in annual_data]
    ipca_factors = get_ipca_adjustment_factors(years)

    yearly_values = [
        (d["year"], float(d["fcf"] * ipca_factors.get(d["year"], Decimal("1"))))
        for d in annual_data
    ]

    cagr_result = compute_cagr(yearly_values)

    if cagr_result["cagr"] is None:
        error = cagr_result["error"]
        if cagr_result["excluded_years"]:
            excluded_str = ", ".join(str(y) for y in cagr_result["excluded_years"])
            error = f"{error} (anos excluídos: {excluded_str})"
        return {**empty, "pfcfPegError": error}

    cagr = cagr_result["cagr"]

    if cagr <= 0:
        return {
            **empty,
            "fcfCAGR": cagr,
            "fcfCAGRMethod": cagr_result["method"],
            "fcfCAGRExcludedYears": cagr_result["excluded_years"],
            "pfcfPegError": "PFCLG não aplicável — crescimento negativo",
        }

    peg = pfcf10 / cagr

    return {
        "pfcfPeg": round(peg, 2),
        "fcfCAGR": cagr,
        "pfcfPegError": None,
        "fcfCAGRMethod": cagr_result["method"],
        "fcfCAGRExcludedYears": cagr_result["excluded_years"],
    }
