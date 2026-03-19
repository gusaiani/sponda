"""Compute historical multiples (P/L10, P/FCL10) alongside price history."""
from datetime import datetime, timezone

from .pe10 import get_annual_earnings
from .pfcf10 import get_annual_fcf

ROLLING_WINDOW = 10


def _rolling_avg(by_year: dict[int, float], year: int) -> float | None:
    """Compute rolling 10-year average ending at `year`.

    Returns None if there are no data points in the window or the average is <= 0.
    """
    values = []
    for y in range(year - ROLLING_WINDOW + 1, year + 1):
        v = by_year.get(y)
        if v is not None:
            values.append(v)
    if not values:
        return None
    avg = sum(values) / len(values)
    return avg if avg > 0 else None


def compute_multiples_history(
    ticker: str,
    historical_prices: list[dict],
    market_cap: float,
    current_price: float,
) -> dict:
    """Build price history + year-end rolling P/L10 and P/FCL10 multiples.

    Shares outstanding is approximated as market_cap / current_price.
    This is a common approximation — share count changes over time are
    not accounted for, but the resulting multiples are directionally correct.

    For each year Y, the multiple is:
        P/L10  = (year_end_price x shares) / avg(net_income from Y-9..Y)
        P/FCL10 = (year_end_price x shares) / avg(fcf from Y-9..Y)

    Returns:
        {
          "prices": [{"date": "2015-01-31", "adjustedClose": 12.34}, ...],
          "multiples": {
            "pl": [{"year": 2015, "value": 8.5}, ...],
            "pfcl": [{"year": 2015, "value": 10.2}, ...]
          }
        }
    """
    if not current_price or current_price <= 0:
        return {"prices": [], "multiples": {"pl": [], "pfcl": []}}

    shares_outstanding = market_cap / current_price

    # Convert prices: unix timestamp → ISO date, keep adjustedClose
    prices = []
    year_end_prices: dict[int, float] = {}

    for point in historical_prices:
        ts = point.get("date")
        adj_close = point.get("adjustedClose")
        if ts is None or adj_close is None:
            continue

        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        iso_date = dt.strftime("%Y-%m-%d")
        prices.append({"date": iso_date, "adjustedClose": round(adj_close, 2)})

        # Track last price seen for each year (monthly data → last month = year-end)
        year = dt.year
        year_end_prices[year] = adj_close

    # Fetch annual earnings and FCF from DB (reuses existing logic)
    earnings_data = get_annual_earnings(ticker, max_years=50)
    fcf_data = get_annual_fcf(ticker, max_years=50)

    earnings_by_year = {d["year"]: float(d["net_income"]) for d in earnings_data}
    fcf_by_year = {d["year"]: float(d["fcf"]) for d in fcf_data}

    # Compute P/L10 per year: (year_end_price × shares) / rolling_avg_net_income
    pl_multiples = []
    for year, price in sorted(year_end_prices.items()):
        avg_income = _rolling_avg(earnings_by_year, year)
        if avg_income is not None:
            market_cap_at_year = price * shares_outstanding
            pl = round(market_cap_at_year / avg_income, 2)
            pl_multiples.append({"year": year, "value": pl})
        else:
            pl_multiples.append({"year": year, "value": None})

    # Compute P/FCL10 per year: (year_end_price × shares) / rolling_avg_fcf
    pfcl_multiples = []
    for year, price in sorted(year_end_prices.items()):
        avg_fcf = _rolling_avg(fcf_by_year, year)
        if avg_fcf is not None:
            market_cap_at_year = price * shares_outstanding
            pfcl = round(market_cap_at_year / avg_fcf, 2)
            pfcl_multiples.append({"year": year, "value": pfcl})
        else:
            pfcl_multiples.append({"year": year, "value": None})

    return {
        "prices": prices,
        "multiples": {
            "pl": pl_multiples,
            "pfcl": pfcl_multiples,
        },
    }
