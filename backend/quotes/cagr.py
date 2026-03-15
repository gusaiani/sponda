"""Robust CAGR calculation using log-linear regression.

Instead of endpoint CAGR ((end/start)^(1/n) - 1), which fails when either
endpoint is negative, we fit ln(value) ~ year on all positive data points.
The slope of the regression is the annualised log growth rate, converted to
a percentage CAGR via (e^slope - 1) * 100.

This approach:
- Uses ALL positive data points, not just endpoints
- Is robust to a single bad year at the start or end
- Is the standard method in financial analysis for estimating growth rates
"""
import math


def compute_cagr(yearly_values: list[tuple[int, float]]) -> dict:
    """Compute CAGR from a list of (year, adjusted_value) pairs.

    Returns dict with:
        cagr: float or None (percentage, e.g. 15.0 = 15%)
        method: "endpoint" | "regression" | None
        error: str or None
        positive_years: int — how many years had positive values
        total_years: int
        excluded_years: list[int] — years excluded (negative/zero values)
    """
    if len(yearly_values) < 2:
        return {
            "cagr": None,
            "method": None,
            "error": "Dados insuficientes para calcular crescimento",
            "positive_years": 0,
            "total_years": len(yearly_values),
            "excluded_years": [],
        }

    # Sort by year ascending
    sorted_vals = sorted(yearly_values, key=lambda x: x[0])

    # Try endpoint CAGR first (preferred when both endpoints are positive)
    oldest_year, oldest_val = sorted_vals[0]
    newest_year, newest_val = sorted_vals[-1]
    n_years = newest_year - oldest_year

    if n_years < 1:
        return {
            "cagr": None,
            "method": None,
            "error": "Dados insuficientes para calcular crescimento",
            "positive_years": 0,
            "total_years": len(sorted_vals),
            "excluded_years": [],
        }

    if oldest_val > 0 and newest_val > 0:
        cagr = ((newest_val / oldest_val) ** (1 / n_years) - 1) * 100
        return {
            "cagr": round(cagr, 2),
            "method": "endpoint",
            "error": None,
            "positive_years": sum(1 for _, v in sorted_vals if v > 0),
            "total_years": len(sorted_vals),
            "excluded_years": [],
        }

    # Endpoint CAGR failed — use log-linear regression on positive years
    positive = [(y, v) for y, v in sorted_vals if v > 0]
    excluded = [y for y, v in sorted_vals if v <= 0]

    if len(positive) < 2:
        neg_years_str = ", ".join(str(y) for y in excluded)
        return {
            "cagr": None,
            "method": None,
            "error": f"Dados insuficientes — anos com valor negativo/zero: {neg_years_str}",
            "positive_years": len(positive),
            "total_years": len(sorted_vals),
            "excluded_years": excluded,
        }

    # OLS: ln(value) = a + b * year  →  b = Σ((x-x̄)(y-ȳ)) / Σ((x-x̄)²)
    xs = [float(y) for y, _ in positive]
    ys = [math.log(v) for _, v in positive]

    n = len(xs)
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)

    if denominator == 0:
        return {
            "cagr": None,
            "method": None,
            "error": "Dados insuficientes para calcular crescimento",
            "positive_years": len(positive),
            "total_years": len(sorted_vals),
            "excluded_years": excluded,
        }

    slope = numerator / denominator
    cagr = (math.exp(slope) - 1) * 100

    return {
        "cagr": round(cagr, 2),
        "method": "regression",
        "error": None,
        "positive_years": len(positive),
        "total_years": len(sorted_vals),
        "excluded_years": excluded,
    }
