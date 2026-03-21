import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { useTickers, TickerItem } from "../hooks/useTickers";
import { useFavorites } from "../hooks/useFavorites";
import { useAuth } from "../hooks/useAuth";
import "../styles/popular.css";

const POPULAR_SYMBOLS = [
  "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3",
  "WEGE3", "ABEV3", "B3SA3", "RENT3", "SUZB3",
  "ITSA4", "ELET3", "JBSS3", "RADL3", "EQTL3",
  "VIVT3", "PRIO3", "LREN3", "TOTS3", "SBSP3",
  "GGBR4", "CSNA3", "CSAN3", "KLBN11", "ENEV3",
  "HAPV3", "RDOR3", "RAIL3", "BBSE3", "CPLE6",
  "UGPA3", "CMIG4", "TAEE11", "EMBR3", "FLRY3",
  "ARZZ3", "MULT3", "PETZ3", "VBBR3", "MGLU3",
];

export function PopularCompanies() {
  const { data: tickers = [] } = useTickers();
  const { isAuthenticated } = useAuth();
  const { favoriteTickers } = useFavorites();

  const companies = useMemo(() => {
    const tickerMap = new Map<string, TickerItem>();
    for (const ticker of tickers) tickerMap.set(ticker.symbol, ticker);

    // Exclude favorited companies from the standard list when user is logged in
    const favoriteSet = isAuthenticated ? new Set(favoriteTickers) : new Set<string>();

    return POPULAR_SYMBOLS
      .filter((symbol) => !favoriteSet.has(symbol))
      .map((symbol) => tickerMap.get(symbol))
      .filter(Boolean) as TickerItem[];
  }, [tickers, isAuthenticated, favoriteTickers]);

  if (companies.length === 0) return null;

  return (
    <div className="popular-grid">
      {companies.map((company) => (
        <Link
          key={company.symbol}
          to="/$ticker"
          params={{ ticker: company.symbol }}
          className="popular-item"
        >
          {company.logo ? (
            <img
              className="popular-logo"
              src={company.logo}
              alt=""
              onError={(event) => {
                (event.target as HTMLImageElement).style.display = "none";
              }}
            />
          ) : (
            <div className="popular-logo-placeholder" />
          )}
          <span className="popular-name">{company.symbol}</span>
        </Link>
      ))}
    </div>
  );
}
