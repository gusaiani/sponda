import { useSavedLists } from "../hooks/useSavedLists";
import { useTranslation } from "../i18n";
import { logoUrl } from "../utils/format";
import Link from "next/link";
import "../styles/saved-lists.css";

const MAX_LOGOS = 5;
const MAX_DISPLAYED_ON_HOME = 3;

export function SavedLists() {
  const { t, locale } = useTranslation();
  const { lists, isLoading } = useSavedLists();

  if (isLoading || lists.length === 0) return null;

  const displayedLists = lists.slice(0, MAX_DISPLAYED_ON_HOME);
  const hasMoreLists = lists.length > MAX_DISPLAYED_ON_HOME;

  return (
    <div className="saved-lists">
      <p className="saved-lists-title">{t("lists.your_lists")}</p>
      <div className="saved-lists-list">
        {displayedLists.map((list) => (
          <SavedListCard key={list.id} list={list} />
        ))}
      </div>
      {hasMoreLists && (
        <p className="saved-lists-see-all">
          <Link href={`/${locale}/listas`} className="saved-lists-see-all-link">
            {t("lists.see_all")}
          </Link>
        </p>
      )}
    </div>
  );
}

interface SavedListCardProps {
  list: { id: number; name: string; tickers: string[]; years: number };
}

export function SavedListCard({ list }: SavedListCardProps) {
  const { t, locale, pluralize } = useTranslation();
  const firstTicker = list.tickers[0];
  const compareUrl = `/${locale}/${firstTicker}/comparar?listId=${list.id}`;
  const displayedTickers = list.tickers.slice(0, MAX_LOGOS);
  const remainingCount = list.tickers.length - MAX_LOGOS;

  return (
    <a
      href={compareUrl}
      className="saved-list-item"
    >
      <div className="saved-list-left">
        <span className="saved-list-name">{list.name}</span>
        <span className="saved-list-dot">·</span>
        <div className="saved-list-logos">
          {displayedTickers.map((ticker) => (
            <img
              key={ticker}
              className="saved-list-logo"
              src={logoUrl(ticker)}
              alt={ticker}
              title={ticker}
              onError={(event) => {
                (event.target as HTMLImageElement).style.display = "none";
              }}
            />
          ))}
          {remainingCount > 0 && (
            <span className="saved-list-more">
              {t("lists.and_more", { count: remainingCount })}
            </span>
          )}
        </div>
      </div>
      <span className="saved-list-detail">
        {t("lists.term", { years: list.years, yearLabel: pluralize(list.years, "common.year_singular", "common.year_plural") })}
      </span>
    </a>
  );
}
