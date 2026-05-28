"""PFCF10 (Price/Free Cash Flow 10-year) calculation logic.

The N-year window covers exactly N×4 trailing quarters; see the docstring
on ``pe10.calculate_pe10`` for the rationale.
"""
from collections import defaultdict
from decimal import Decimal

from .fx import market_cap_in_reported_currency
from .inflation import get_inflation_adjustment_factors
from .models import QuarterlyCashFlow


def get_annual_fcf(ticker: str, max_years: int = 10) -> list[dict]:
    """
    Return annual FCF breakdowns covering the trailing ``max_years * 4``
    quarters, grouped by calendar year. Caller divides by ``max_years``
    (NOT ``len(result)``) when computing the average — see pe10 for the
    rationale.
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

    return [
        {
            "year": year,
            "fcf": data["fcf"],
            "quarters": data["quarters"],
            "quarterly_detail": sorted(data["quarterly_detail"], key=lambda x: x["end_date"]),
        }
        for year, data in sorted(yearly.items(), reverse=True)
    ]


def calculate_pfcf10(ticker: str, market_cap: Decimal, max_years: int = 10) -> dict:
    """
    Calculate PFCF10 for a given ticker using Market Cap / Avg Adjusted FCF.

    FCF = Operating Cash Flow + Investing Cash Flow
    PFCF10 = Market Cap / Average Inflation-Adjusted Annual FCF (10 years)
    """
    annual_data = get_annual_fcf(ticker, max_years=max_years)

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

    total_quarters = sum(d["quarters"] for d in annual_data)
    effective_years = min(max_years, total_quarters // 4)
    if effective_years == 0:
        return {
            "pfcf10": None,
            "avg_adjusted_fcf": None,
            "years_of_data": 0,
            "label": "PFCF0",
            "error": "Sem dados de fluxo de caixa disponíveis",
            "annual_data_flag": False,
            "calculation_details": [],
        }
    target_quarters = effective_years * 4

    years = [d["year"] for d in annual_data]
    ipca_factors = get_inflation_adjustment_factors(ticker, years)

    adjusted_values: list[Decimal] = []
    yearly_breakdown = []
    collected = 0

    for year_data in annual_data:
        if collected >= target_quarters:
            break
        remaining = target_quarters - collected
        year = year_data["year"]
        factor = ipca_factors.get(year, Decimal("1"))

        if year_data["quarters"] <= remaining:
            adjusted = year_data["fcf"] * factor
            adjusted_values.append(adjusted)
            yearly_breakdown.append({
                "year": year,
                "nominalFCF": float(year_data["fcf"]),
                "ipcaFactor": round(float(factor), 6),
                "adjustedFCF": float(adjusted),
                "quarters": year_data["quarters"],
                "quarterlyDetail": year_data["quarterly_detail"],
            })
            collected += year_data["quarters"]
        else:
            taken = year_data["quarterly_detail"][-remaining:]
            partial_nominal = sum(
                (Decimal(str(q["fcf"])) for q in taken),
                Decimal("0"),
            )
            partial_adjusted = partial_nominal * factor
            adjusted_values.append(partial_adjusted)
            yearly_breakdown.append({
                "year": year,
                "nominalFCF": float(partial_nominal),
                "ipcaFactor": round(float(factor), 6),
                "adjustedFCF": float(partial_adjusted),
                "quarters": len(taken),
                "quarterlyDetail": taken,
            })
            collected = target_quarters

    years_of_data = effective_years
    label = f"PFCF{years_of_data}"

    avg_quarters = sum(b["quarters"] for b in yearly_breakdown) / len(yearly_breakdown)
    annual_data_flag = avg_quarters < 2

    avg_adjusted = sum(adjusted_values) / Decimal(str(years_of_data))

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
            "error": "FCL médio negativo",
        }

    market_cap_reported = market_cap_in_reported_currency(market_cap, ticker)
    if market_cap_reported is None:
        return {
            **base_result,
            "pfcf10": None,
            "avg_adjusted_fcf": float(avg_adjusted),
            "error": "Câmbio indisponível para a moeda de relatório",
        }

    pfcf10 = market_cap_reported / avg_adjusted

    return {
        **base_result,
        "pfcf10": round(float(pfcf10), 2),
        "avg_adjusted_fcf": float(avg_adjusted),
        "error": None,
    }
