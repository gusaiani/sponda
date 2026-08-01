"""PFCF10 (Price/Free Cash Flow 10-year) calculation logic.

The N-year window covers exactly N × periods_per_year trailing filings;
see the docstring on ``pe10.calculate_pe10`` for the rationale.
"""
from collections import defaultdict
from decimal import Decimal

from .fx import market_cap_in_reported_currency
from .inflation import get_inflation_adjustment_factors
from .models import QuarterlyCashFlow
from .reporting_frequency import QUARTERLY_PERIODS_PER_YEAR, infer_periods_per_year


def _quarter_free_cash_flow(quarter: QuarterlyCashFlow) -> Decimal | None:
    """
    One FCF definition for the whole app, matching fundamentals.py:
    prefer the provider's explicit free cash flow (OCF − CapEx); fall
    back to OCF + investing CF when the provider doesn't send it.
    The fallback overstates outflows for companies that park cash in
    securities (their purchases sit in investing CF), which is why the
    explicit figure wins when available.
    """
    if quarter.free_cash_flow is not None:
        return Decimal(str(quarter.free_cash_flow))
    if quarter.operating_cash_flow is not None:
        operating = Decimal(str(quarter.operating_cash_flow))
        investing = Decimal(str(quarter.investment_cash_flow or 0))
        return operating + investing
    return None


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
        fcf = _quarter_free_cash_flow(q)
        if fcf is None:
            continue
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

    FCF = provider free cash flow (OCF − CapEx), falling back to
    Operating Cash Flow + Investing Cash Flow.
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
            "periods_per_year": QUARTERLY_PERIODS_PER_YEAR,
            "calculation_details": [],
        }

    periods_per_year = infer_periods_per_year(annual_data)
    total_periods = sum(d["quarters"] for d in annual_data)
    effective_years = min(max_years, total_periods // periods_per_year)
    if effective_years == 0:
        return {
            "pfcf10": None,
            "avg_adjusted_fcf": None,
            "years_of_data": 0,
            "label": "PFCF0",
            "error": "Sem dados de fluxo de caixa disponíveis",
            "annual_data_flag": False,
            "periods_per_year": periods_per_year,
            "calculation_details": [],
        }
    target_periods = effective_years * periods_per_year

    years = [d["year"] for d in annual_data]
    ipca_factors = get_inflation_adjustment_factors(ticker, years)

    adjusted_values: list[Decimal] = []
    yearly_breakdown = []
    collected = 0

    for year_data in annual_data:
        if collected >= target_periods:
            break
        remaining = target_periods - collected
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
            collected = target_periods

    years_of_data = effective_years
    label = f"PFCF{years_of_data}"

    annual_data_flag = periods_per_year == 1

    avg_adjusted = sum(adjusted_values) / Decimal(str(years_of_data))

    base_result = {
        "years_of_data": years_of_data,
        "label": label,
        "annual_data_flag": annual_data_flag,
        "periods_per_year": periods_per_year,
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
