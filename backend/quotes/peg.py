"""PEG ratio (Peter Lynch) calculation logic — using PE10."""
from decimal import Decimal

from .pe10 import get_annual_earnings, get_ipca_adjustment_factors


def calculate_peg(ticker: str, pe10: float | None) -> dict:
    """
    Calculate PEG ratio: PE10 ÷ earnings CAGR (%).

    Uses inflation-adjusted annual earnings to compute the CAGR
    from oldest to newest year available.

    Returns dict with:
        peg: float or None
        earningsCAGR: float or None (percentage, e.g. 15.0 = 15%)
        pegError: str or None
    """
    if pe10 is None:
        return {
            "peg": None,
            "earningsCAGR": None,
            "pegError": "PE10 indisponível",
        }

    annual_data = get_annual_earnings(ticker)
    if len(annual_data) < 2:
        return {
            "peg": None,
            "earningsCAGR": None,
            "pegError": "Dados insuficientes para calcular crescimento",
        }

    years = [d["year"] for d in annual_data]
    ipca_factors = get_ipca_adjustment_factors(years)

    # annual_data is sorted by year desc — most recent first
    newest = annual_data[0]
    oldest = annual_data[-1]

    newest_adjusted = float(newest["net_income"] * ipca_factors.get(newest["year"], Decimal("1")))
    oldest_adjusted = float(oldest["net_income"] * ipca_factors.get(oldest["year"], Decimal("1")))

    if oldest_adjusted <= 0 or newest_adjusted <= 0:
        return {
            "peg": None,
            "earningsCAGR": None,
            "pegError": "Crescimento não calculável (lucro negativo no período)",
        }

    n_years = newest["year"] - oldest["year"]
    if n_years < 1:
        return {
            "peg": None,
            "earningsCAGR": None,
            "pegError": "Dados insuficientes para calcular crescimento",
        }

    cagr = ((newest_adjusted / oldest_adjusted) ** (1 / n_years) - 1) * 100

    if cagr <= 0:
        return {
            "peg": None,
            "earningsCAGR": round(cagr, 2),
            "pegError": "PEG não aplicável — crescimento negativo",
        }

    peg = pe10 / cagr

    return {
        "peg": round(peg, 2),
        "earningsCAGR": round(cagr, 2),
        "pegError": None,
    }
