import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { useFavorites } from "../hooks/useFavorites";
import { useTickers, TickerItem } from "../hooks/useTickers";
import "../styles/popular.css";

interface FavoriteDisplayItem {
  symbol: string;
  logo: string;
}

export function FavoriteCompanies() {
  const { favoriteTickers, isLoading: favoritesLoading } = useFavorites();
  const { data: allTickers = [] } = useTickers();

  const favoriteCompanies = useMemo((): FavoriteDisplayItem[] => {
    if (!favoriteTickers.length) return [];
    const tickerMap = new Map<string, TickerItem>();
    for (const ticker of allTickers) tickerMap.set(ticker.symbol, ticker);

    return favoriteTickers.map((symbol) => {
      const tickerData = tickerMap.get(symbol);
      return {
        symbol,
        logo: tickerData?.logo ?? "",
      };
    });
  }, [favoriteTickers, allTickers]);

  if (favoritesLoading || favoriteCompanies.length === 0) return null;

  return (
    <>
      <p className="favorites-section-title">Favoritas</p>
      <div className="favorites-grid">
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
    </>
  );
}
