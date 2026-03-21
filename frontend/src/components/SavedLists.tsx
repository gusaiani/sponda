import { Link } from "@tanstack/react-router";
import { useSavedLists } from "../hooks/useSavedLists";
import "../styles/saved-lists.css";

export function SavedLists() {
  const { lists, isLoading, deleteList } = useSavedLists();

  if (isLoading || lists.length === 0) return null;

  return (
    <div className="saved-lists">
      <p className="saved-lists-title">Suas listas</p>
      <div className="saved-lists-list">
        {lists.map((list) => {
          const firstTicker = list.tickers[0];
          const compareUrl = `/${firstTicker}/comparar`;

          return (
            <div key={list.id} className="saved-list-item">
              <Link
                to={compareUrl}
                className="saved-list-link"
              >
                <span className="saved-list-name">{list.name}</span>
                <span className="saved-list-detail">
                  {list.tickers.length} empresas · {list.years} {list.years === 1 ? "ano" : "anos"}
                </span>
              </Link>
              <button
                className="saved-list-delete"
                onClick={() => deleteList.mutate(list.id)}
                aria-label={`Remover ${list.name}`}
                title="Remover"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
