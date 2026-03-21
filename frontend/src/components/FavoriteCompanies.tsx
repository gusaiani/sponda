import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { useFavorites } from "../hooks/useFavorites";
import { useTickers, TickerItem } from "../hooks/useTickers";
import "../styles/popular.css";

export function FavoriteCompanies() {
  const { favoriteTickers, isLoading: favoritesLoading } = useFavorites();
  const { data: allTickers = [] } = useTickers();

  const favoriteCompanies = useMemo(() => {
    if (!favoriteTickers.length || !allTickers.length) return [];
    const tickerMap = new Map<string, TickerItem>();
    for (const ticker of allTickers) tickerMap.set(ticker.symbol, ticker);
    return favoriteTickers
      .map((symbol) => tickerMap.get(symbol))
      .filter(Boolean) as TickerItem[];
  }, [favoriteTickers, allTickers]);

  if (favoritesLoading || favoriteCompanies.length === 0) return null;

  return (
    <div style={{ marginBottom: "1.5rem" }}>
      <p className="favorites-section-title">Seus favoritos</p>
      <div className="popular-grid">
        {favoriteCompanies.map((company) => (
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
    </div>
  );
}
