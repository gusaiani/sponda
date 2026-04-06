import Link from "next/link";
import { useFavorites } from "../hooks/useFavorites";
import { useTranslation } from "../i18n";
import { logoUrl } from "../utils/format";
import "../styles/popular.css";

export function FavoriteCompanies() {
  const { t } = useTranslation();
  const { favoriteTickers, isLoading: favoritesLoading } = useFavorites();

  if (favoritesLoading || favoriteTickers.length === 0) return null;

  return (
    <>
      <p className="favorites-section-title">{t("favorites.title")}</p>
      <div className="favorites-grid">
        {favoriteTickers.map((symbol) => (
          <Link
            key={symbol}
            href={`/${symbol}`}
            className="popular-item"
          >
            <img
              className="popular-logo"
              src={logoUrl(symbol)}
              alt=""
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
