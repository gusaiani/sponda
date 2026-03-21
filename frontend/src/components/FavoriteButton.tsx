import { useAuth } from "../hooks/useAuth";
import { useFavorites } from "../hooks/useFavorites";
import "../styles/favorite-button.css";

interface FavoriteButtonProps {
  ticker: string;
}

export function FavoriteButton({ ticker }: FavoriteButtonProps) {
  const { isAuthenticated } = useAuth();
  const { isFavorite, toggleFavorite } = useFavorites();

  if (!isAuthenticated) return null;

  const favorited = isFavorite(ticker);

  return (
    <button
      className={`favorite-button ${favorited ? "favorite-button-active" : ""}`}
      onClick={() => toggleFavorite(ticker)}
      aria-label={favorited ? "Remover dos favoritos" : "Adicionar aos favoritos"}
      title={favorited ? "Remover dos favoritos" : "Adicionar aos favoritos"}
    >
      {favorited ? "★" : "☆"}
    </button>
  );
}
