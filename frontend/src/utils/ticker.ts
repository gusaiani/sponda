/**
 * Brazilian tickers end with one or more digits: PETR4, VALE3, SANB11.
 * US tickers are all letters: AAPL, MSFT, GOOGL.
 */
export function isBrazilianTicker(ticker: string): boolean {
  return /^[A-Z]+\d+$/i.test(ticker);
}
