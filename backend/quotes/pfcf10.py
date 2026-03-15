"""PFCF10 (Price/Free Cash Flow 10-year) calculation logic."""
from collections import defaultdict
from decimal import Decimal

from .models import QuarterlyCashFlow
from .pe10 import get_ipca_adjustment_factors


def get_annual_fcf(ticker: str, max_years: int = 10) -> list[dict]:
    """
    Get annual FCF by summing quarterly (operating + investing) cash flows.
    Returns list of {"year": int, "fcf": Decimal, "quarters": int,
                     "quarterly_detail": list} sorted by year desc.
    """
    quarters = QuarterlyCashFlow.objects.filter(
        ticker=ticker.upper(),
    ).order_by("-end_date")[: max_years * 4]

    yearly = defaultdict(lambda: {"fcf": Decimal("0"), "quarters": 0, "quarterly_detail": []})
    for q in quarters:
        if q.operating_cash_flow is None:
            continue
        ocf = Decimal(str(q.operating_cash_flow))
        icf = Decimal(str(q.investment_cash_flow or 0))
        fcf = ocf + icf
        year = q.end_date.year
        yearly[year]["fcf"] += fcf
        yearly[year]["quarters"] += 1
        yearly[year]["quarterly_detail"].append({
            "end_date": q.end_date.isoformat(),
            "operating_cash_flow": q.operating_cash_flow,
            "investment_cash_flow": q.investment_cash_flow,
            "fcf": float(fcf),
        })

    result = [
        {
            "year": year,
            "fcf": data["fcf"],
            "quarters": data["quarters"],
            "quarterly_detail": sorted(data["quarterly_detail"], key=lambda x: x["end_date"]),
        }
        for year, data in sorted(yearly.items(), reverse=True)
    ]
    return result[:max_years]


def calculate_pfcf10(ticker: str, market_cap: Decimal) -> dict:
    """
    Calculate PFCF10 for a given ticker using Market Cap / Avg Adjusted FCF.

    FCF = Operating Cash Flow + Investing Cash Flow
    PFCF10 = Market Cap / Average Inflation-Adjusted Annual FCF (10 years)
    """
    annual_data = get_annual_fcf(ticker)

    if not annual_data:
        return {
            "pfcf10": None,
            "avg_adjusted_fcf": None,
            "years_of_data": 0,
            "label": "PFCF0",
            "error": "Sem dados de fluxo de caixa disponíveis",
            "annual_data_flag": False,
            "calculation_details": [],
        }

    years = [d["year"] for d in annual_data]
    ipca_factors = get_ipca_adjustment_factors(years)

    adjusted_values = []
    yearly_breakdown = []
    for year_data in annual_data:
        fcf = year_data["fcf"]
        year = year_data["year"]
        factor = ipca_factors.get(year, Decimal("1"))
        adjusted = fcf * factor
        adjusted_values.append(adjusted)
        yearly_breakdown.append({
            "year": year,
            "nominalFCF": float(fcf),
            "ipcaFactor": round(float(factor), 6),
            "adjustedFCF": float(adjusted),
            "quarters": year_data["quarters"],
            "quarterlyDetail": year_data["quarterly_detail"],
        })

    years_of_data = len(adjusted_values)
    label = f"PFCF{years_of_data}"

    avg_quarters = sum(d["quarters"] for d in annual_data) / len(annual_data)
    annual_data_flag = avg_quarters < 2

    avg_adjusted = sum(adjusted_values) / len(adjusted_values)

    base_result = {
        "years_of_data": years_of_data,
        "label": label,
        "annual_data_flag": annual_data_flag,
        "calculation_details": yearly_breakdown,
    }

    if avg_adjusted <= 0:
        return {
            **base_result,
            "pfcf10": None,
            "avg_adjusted_fcf": float(avg_adjusted),
            "error": "N/A — fluxo de caixa livre médio negativo no período",
        }

    pfcf10 = market_cap / avg_adjusted

    return {
        **base_result,
        "pfcf10": round(float(pfcf10), 2),
        "avg_adjusted_fcf": float(avg_adjusted),
        "error": None,
    }
