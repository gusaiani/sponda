import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useFavorites } from "../hooks/useFavorites";
import { AuthModal } from "./AuthModal";
import "../styles/favorite-button.css";

interface FavoriteButtonProps {
  ticker: string;
}

export function FavoriteButton({ ticker }: FavoriteButtonProps) {
  const { isAuthenticated } = useAuth();
  const { isFavorite, toggleFavorite, favorites } = useFavorites();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const queryClient = useQueryClient();

  const favorited = isAuthenticated && isFavorite(ticker);
  const showProminent = !favorited && (!isAuthenticated || favorites.length < 3);

  function handleClick() {
    if (!isAuthenticated) {
      setShowAuthModal(true);
      return;
    }
    toggleFavorite(ticker);
  }

  function handleAuthSuccess() {
    setShowAuthModal(false);
    // Refresh auth state, then favorite
    queryClient.invalidateQueries({ queryKey: ["auth-user"] }).then(() => {
      toggleFavorite(ticker);
    });
  }

  if (showProminent) {
    return (
      <>
        <button
          className="favorite-button-prominent"
          onClick={handleClick}
          aria-label="Adicionar a Favoritos"
          title="Adicionar a Favoritos"
        >
          <span className="favorite-button-prominent-star">☆</span>
          <span className="favorite-button-prominent-label">Adicionar a Favoritos</span>
        </button>

        {showAuthModal && (
          <AuthModal
            onSuccess={handleAuthSuccess}
            onClose={() => setShowAuthModal(false)}
          />
        )}
      </>
    );
  }

  return (
    <>
      <button
        className={`favorite-button ${favorited ? "favorite-button-active" : ""}`}
        onClick={handleClick}
        aria-label={favorited ? "Remover dos favoritos" : "Adicionar aos favoritos"}
        title={favorited ? "Remover dos favoritos" : "Adicionar aos favoritos"}
      >
        {favorited ? "★" : "☆"}
      </button>

      {showAuthModal && (
        <AuthModal
          onSuccess={handleAuthSuccess}
          onClose={() => setShowAuthModal(false)}
        />
      )}
    </>
  );
}
