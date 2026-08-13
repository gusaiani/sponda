"""Indicator computation service used by the screener and alert checker.

Wraps the existing PE10/PFCF10/leverage/PEG calculators behind a single call
that returns a dict keyed by :class:`IndicatorSnapshot` field names. Missing
data never raises — each individual indicator falls back to ``None``.
"""
from decimal import Decimal
from typing import Optional

from .leverage import calculate_leverage
from .pe10 import PE_WINDOW_YEARS, calculate_pe_windows
from .peg import calculate_peg
from .pfcf10 import calculate_pfcf10
from .pfcf_peg import calculate_pfcf_peg


def _to_decimal(value) -> Optional[Decimal]:
    """Convert a float / int / Decimal / None into a Decimal (or None)."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_company_indicators(
    ticker: str,
    market_cap: Optional[int] = None,
    current_price: Optional[Decimal] = None,
) -> dict:
    """Compute every indicator the screener knows about for one ticker.

    Parameters
    ----------
    ticker:
        Company symbol. Case-insensitive — normalized to upper-case.
    market_cap:
        Latest market capitalization (BRL or USD cents depending on market).
        Required for PE10 / PFCF10 / PEG / PFCLG. If ``None``, those fields
        come back as ``None`` but leverage ratios are still computed.
    current_price:
        Optional reference price. Passed through to the returned dict; the
        screener stores it alongside the snapshot for display.

    Returns
    -------
    dict
        Keys match :class:`quotes.models.IndicatorSnapshot` field names:
        the strict P/E windows ``pe1``..``pe15`` plus ``pe_years_available``,
        ``pfcf10``, ``peg``, ``pfcf_peg``, ``debt_to_equity``,
        ``debt_ex_lease_to_equity``, ``liabilities_to_equity``,
        ``current_ratio``, ``debt_to_avg_earnings``, ``debt_to_avg_fcf``,
        ``market_cap``, ``current_price``. Any indicator that cannot be
        computed from available data is ``None``.
    """
    ticker = ticker.upper()

    market_cap_decimal = None
    if market_cap is not None:
        market_cap_decimal = Decimal(str(market_cap))

    # The P/E windows need a market cap to produce values, but the pass
    # still runs without one so pe_years_available reflects the data.
    pe_windows_result = calculate_pe_windows(ticker, market_cap_decimal)
    if market_cap_decimal is not None:
        pfcf10_result = calculate_pfcf10(ticker, market_cap_decimal, max_years=10)
    else:
        pfcf10_result = {"pfcf10": None, "avg_adjusted_fcf": None}

    leverage_result = calculate_leverage(ticker)

    # PEG / PFCLG can only run when their base multiple exists.
    pe_by_years = pe_windows_result["pe_by_years"]
    pe10_value = pe_by_years.get(10)
    pfcf10_value = pfcf10_result.get("pfcf10")
    peg_result = (
        calculate_peg(ticker, pe10_value, max_years=10)
        if pe10_value is not None
        else {"peg": None}
    )
    pfcf_peg_result = (
        calculate_pfcf_peg(ticker, pfcf10_value, max_years=10)
        if pfcf10_value is not None
        else {"pfcfPeg": None}
    )

    # Debt coverage uses gross debt against long-run average earnings / FCF.
    total_debt = leverage_result.get("totalDebt")
    avg_earnings = pe_windows_result.get("avg_adjusted_net_income")
    avg_fcf = pfcf10_result.get("avg_adjusted_fcf")

    debt_to_avg_earnings = None
    if total_debt is not None and avg_earnings and avg_earnings > 0:
        debt_to_avg_earnings = Decimal(str(total_debt)) / Decimal(str(avg_earnings))

    debt_to_avg_fcf = None
    if total_debt is not None and avg_fcf and avg_fcf > 0:
        debt_to_avg_fcf = Decimal(str(total_debt)) / Decimal(str(avg_fcf))

    pe_window_fields = {
        f"pe{years}": _to_decimal(pe_by_years.get(years)) for years in PE_WINDOW_YEARS
    }

    return {
        **pe_window_fields,
        "pe_years_available": pe_windows_result["years_available"],
        "pfcf10": _to_decimal(pfcf10_value),
        "peg": _to_decimal(peg_result.get("peg")),
        "pfcf_peg": _to_decimal(pfcf_peg_result.get("pfcfPeg")),
        "debt_to_equity": _to_decimal(leverage_result.get("debtToEquity")),
        "debt_ex_lease_to_equity": _to_decimal(
            leverage_result.get("debtExLeaseToEquity"),
        ),
        "liabilities_to_equity": _to_decimal(leverage_result.get("liabilitiesToEquity")),
        "current_ratio": _to_decimal(leverage_result.get("currentRatio")),
        "debt_to_avg_earnings": _to_decimal(debt_to_avg_earnings),
        "debt_to_avg_fcf": _to_decimal(debt_to_avg_fcf),
        "market_cap": market_cap,
        "current_price": current_price,
    }
