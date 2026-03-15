"""PFCLG (Price/FCF-to-Growth) ratio — Peter Lynch PEG applied to free cash flow."""
from decimal import Decimal

from .pe10 import get_ipca_adjustment_factors
from .pfcf10 import get_annual_fcf


def calculate_pfcf_peg(ticker: str, pfcf10: float | None) -> dict:
    """
    Calculate PFCLG ratio: PFCF10 ÷ FCF CAGR (%).

    Uses inflation-adjusted annual FCF to compute the CAGR
    from oldest to newest year available.

    Returns dict with:
        pfcfPeg: float or None
        fcfCAGR: float or None (percentage, e.g. 15.0 = 15%)
        pfcfPegError: str or None
    """
    if pfcf10 is None:
        return {
            "pfcfPeg": None,
            "fcfCAGR": None,
            "pfcfPegError": "PFCF10 indisponível",
        }

    annual_data = get_annual_fcf(ticker)
    if len(annual_data) < 2:
        return {
            "pfcfPeg": None,
            "fcfCAGR": None,
            "pfcfPegError": "Dados insuficientes para calcular crescimento",
        }

    years = [d["year"] for d in annual_data]
    ipca_factors = get_ipca_adjustment_factors(years)

    # annual_data is sorted by year desc — most recent first
    newest = annual_data[0]
    oldest = annual_data[-1]

    newest_adjusted = float(newest["fcf"] * ipca_factors.get(newest["year"], Decimal("1")))
    oldest_adjusted = float(oldest["fcf"] * ipca_factors.get(oldest["year"], Decimal("1")))

    if oldest_adjusted <= 0 or newest_adjusted <= 0:
        return {
            "pfcfPeg": None,
            "fcfCAGR": None,
            "pfcfPegError": "Crescimento não calculável (FCF negativo no período)",
        }

    n_years = newest["year"] - oldest["year"]
    if n_years < 1:
        return {
            "pfcfPeg": None,
            "fcfCAGR": None,
            "pfcfPegError": "Dados insuficientes para calcular crescimento",
        }

    cagr = ((newest_adjusted / oldest_adjusted) ** (1 / n_years) - 1) * 100

    if cagr <= 0:
        return {
            "pfcfPeg": None,
            "fcfCAGR": round(cagr, 2),
            "pfcfPegError": "PFCLG não aplicável — crescimento negativo",
        }

    peg = pfcf10 / cagr

    return {
        "pfcfPeg": round(peg, 2),
        "fcfCAGR": round(cagr, 2),
        "pfcfPegError": None,
    }
