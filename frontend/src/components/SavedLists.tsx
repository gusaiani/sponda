import { useMemo } from "react";
import { Link } from "@tanstack/react-router";
import { useSavedLists } from "../hooks/useSavedLists";
import { useTickers, TickerItem } from "../hooks/useTickers";
import "../styles/saved-lists.css";

const MAX_LOGOS = 5;

export function SavedLists() {
  const { lists, isLoading } = useSavedLists();
  const { data: allTickers = [] } = useTickers();

  const tickerMap = useMemo(() => {
    const map = new Map<string, TickerItem>();
    for (const ticker of allTickers) map.set(ticker.symbol, ticker);
    return map;
  }, [allTickers]);

  if (isLoading || lists.length === 0) return null;

  return (
    <div className="saved-lists">
      <p className="saved-lists-title">Suas listas</p>
      <div className="saved-lists-list">
        {lists.map((list) => {
          const firstTicker = list.tickers[0];
          const compareUrl = `/${firstTicker}/comparar`;
          const displayedTickers = list.tickers.slice(0, MAX_LOGOS);
          const remainingCount = list.tickers.length - MAX_LOGOS;

          return (
            <Link
              key={list.id}
              to={compareUrl}
              search={{ listId: String(list.id) }}
              className="saved-list-item"
            >
              <div className="saved-list-left">
                <span className="saved-list-name">{list.name}</span>
                <span className="saved-list-dot">·</span>
                <div className="saved-list-logos">
                  {displayedTickers.map((ticker) => {
                    const tickerData = tickerMap.get(ticker);
                    return tickerData?.logo ? (
                      <img
                        key={ticker}
                        className="saved-list-logo"
                        src={tickerData.logo}
                        alt={ticker}
                        title={ticker}
                        onError={(event) => {
                          (event.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    ) : (
                      <div key={ticker} className="saved-list-logo-placeholder" title={ticker} />
                    );
                  })}
                  {remainingCount > 0 && (
                    <span className="saved-list-more">
                      e mais {remainingCount}
                    </span>
                  )}
                </div>
              </div>
              <span className="saved-list-detail">
                Prazo: {list.years} {list.years === 1 ? "ano" : "anos"}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
