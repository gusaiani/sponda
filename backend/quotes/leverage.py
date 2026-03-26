"""Leverage indicators from the most recent balance sheet."""
from .models import BalanceSheet


def calculate_leverage(ticker: str) -> dict:
    """
    Calculate leverage ratios from the most recent balance sheet.

    Returns:
    - debtToEquity: Dívida Bruta / Patrimônio Líquido
    - liabilitiesToEquity: Passivo Total / Patrimônio Líquido
    - currentRatio: Ativo Circulante / Passivo Circulante
    """
    latest = (
        BalanceSheet.objects.filter(ticker=ticker.upper())
        .order_by("-end_date")
        .first()
    )

    if not latest:
        return {
            "debtToEquity": None,
            "debtExLeaseToEquity": None,
            "liabilitiesToEquity": None,
            "currentRatio": None,
            "leverageError": "Dados de balanço indisponíveis",
            "leverageDate": None,
            "totalDebt": None,
            "totalLease": None,
            "totalLiabilities": None,
            "stockholdersEquity": None,
        }

    equity = latest.stockholders_equity
    total_debt = latest.total_debt
    total_lease = latest.total_lease
    total_liab = latest.total_liabilities
    end_date = latest.end_date.isoformat()

    base = {
        "leverageDate": end_date,
        "totalDebt": total_debt,
        "totalLease": total_lease,
        "totalLiabilities": total_liab,
        "stockholdersEquity": equity,
    }

    current_ratio = None
    if latest.current_assets is not None and latest.current_liabilities is not None and latest.current_liabilities != 0:
        current_ratio = round(latest.current_assets / latest.current_liabilities, 2)

    if equity is None or equity == 0:
        return {
            **base,
            "debtToEquity": None,
            "debtExLeaseToEquity": None,
            "liabilitiesToEquity": None,
            "currentRatio": current_ratio,
            "leverageError": "Patrimônio líquido indisponível ou zero",
        }

    error = None
    debt_to_equity = None
    debt_ex_lease_to_equity = None
    liab_to_equity = None

    if total_debt is not None:
        debt_to_equity = round(total_debt / equity, 2)
        if total_lease is not None:
            debt_ex_lease_to_equity = round((total_debt - total_lease) / equity, 2)

    if total_liab is not None:
        liab_to_equity = round(total_liab / equity, 2)

    if debt_to_equity is None and liab_to_equity is None:
        error = "Dados de dívida e passivo indisponíveis"

    return {
        **base,
        "debtToEquity": debt_to_equity,
        "debtExLeaseToEquity": debt_ex_lease_to_equity,
        "liabilitiesToEquity": liab_to_equity,
        "currentRatio": current_ratio,
        "leverageError": error,
    }
