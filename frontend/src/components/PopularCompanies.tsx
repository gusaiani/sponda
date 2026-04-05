import { useMemo } from "react";
import Link from "next/link";
import { useTickers, TickerItem } from "../hooks/useTickers";
import { useFavorites } from "../hooks/useFavorites";
import { useAuth } from "../hooks/useAuth";
import { useRegion } from "../hooks/useRegion";
import { useTranslation } from "../i18n";
import { getPopularSymbols } from "../utils/suggestedCompanies";
import "../styles/popular.css";

const MAX_DISPLAYED = 40;

export function PopularCompanies() {
  const { t } = useTranslation();
  const { data: tickers = [] } = useTickers();
  const { isAuthenticated } = useAuth();
  const { favoriteTickers } = useFavorites();
  const region = useRegion();

  const companies = useMemo(() => {
    const tickerMap = new Map<string, TickerItem>();
    for (const ticker of tickers) tickerMap.set(ticker.symbol, ticker);

    const favoriteSet = isAuthenticated ? new Set(favoriteTickers) : new Set<string>();
    const popularSymbols = getPopularSymbols(region);

    return popularSymbols
      .filter((symbol) => !favoriteSet.has(symbol))
      .map((symbol) => tickerMap.get(symbol))
      .filter(Boolean)
      .slice(0, MAX_DISPLAYED) as TickerItem[];
  }, [tickers, isAuthenticated, favoriteTickers, region]);

  if (companies.length === 0) return null;

  const hasFavorites = isAuthenticated && favoriteTickers.length > 0;

  return (
    <>
    <p className={`popular-section-title ${hasFavorites ? "" : "popular-section-title-standalone"}`}>{t("popular.title")}</p>
    <div className="popular-grid">
      {companies.map((company) => (
        <Link
          key={company.symbol}
          href={`/${company.symbol}`}
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
