import { useMemo } from "react";
import Link from "next/link";
import { useFavorites } from "../hooks/useFavorites";
import { useAuth } from "../hooks/useAuth";
import { useRegion } from "../hooks/useRegion";
import { useTranslation } from "../i18n";
import { getPopularSymbols } from "../utils/suggestedCompanies";
import { logoUrl } from "../utils/format";
import "../styles/popular.css";

const MAX_DISPLAYED = 40;

export function PopularCompanies() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { favoriteTickers } = useFavorites();
  const region = useRegion();

  const symbols = useMemo(() => {
    const favoriteSet = isAuthenticated ? new Set(favoriteTickers) : new Set<string>();
    return getPopularSymbols(region)
      .filter((symbol) => !favoriteSet.has(symbol))
      .slice(0, MAX_DISPLAYED);
  }, [isAuthenticated, favoriteTickers, region]);

  if (symbols.length === 0) return null;

  const hasFavorites = isAuthenticated && favoriteTickers.length > 0;

  return (
    <>
    <p className={`popular-section-title ${hasFavorites ? "" : "popular-section-title-standalone"}`}>{t("popular.title")}</p>
    <div className="popular-grid">
      {symbols.map((symbol) => (
        <Link
          key={symbol}
          href={`/${symbol}`}
          className="popular-item"
        >
          <img
            className="popular-logo"
            src={logoUrl(symbol)}
            alt=""
            loading="lazy"
            onError={(event) => {
              (event.target as HTMLImageElement).style.display = "none";
            }}
          />
          <span className="popular-name">{symbol}</span>
        </Link>
      ))}
    </div>
    </>
  );
}
