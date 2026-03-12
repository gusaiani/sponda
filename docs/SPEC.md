# Sponda — PE10 Valuation App for Brazilian Stocks

## What

Sponda calculates PE10 (Shiller P/E) for Brazilian stocks using BRAPI data. Users enter a ticker and see the inflation-adjusted price-to-earnings ratio over a 10-year rolling window.

## Why

Long-term value investors need tools to identify overvalued/undervalued companies. PE10 smooths earnings volatility by using a decade of earnings data, making it more reliable than single-year P/E ratios.

## PE10 Formula

```
PE10 = Current Share Price / Average Inflation-Adjusted Annual EPS (10 years)
```

### Steps
1. Fetch quarterly income statements from BRAPI
2. Extract `basicEarningsPerCommonShare` (fallback: `netIncome / sharesOutstanding`)
3. Take 40 most recent quarters, sum EPS by calendar year
4. Inflation-adjust each year's EPS using cumulative IPCA index
5. Average the 10 adjusted annual EPS values
6. PE10 = `regularMarketPrice` / average adjusted EPS

### Edge Cases
- Negative average earnings → display "N/A"
- Less than 40 quarters → label as "PE-N" (e.g., PE7)
- Null EPS fields → skip quarter, note incomplete data

## Rate Limiting

3 free lookups/day per session cookie. After that, require signup.

## Stack

- **Backend:** Django + DRF + PostgreSQL
- **Frontend:** React + TypeScript + Vite + TanStack Query/Router
- **Styling:** Tailwind CSS with `@apply` only (no utility classes in JSX)
- **Deploy:** Docker Compose on Digital Ocean, Nginx reverse proxy, GitHub Actions CI/CD
