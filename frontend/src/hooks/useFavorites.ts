import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";
import { buildApiError } from "../utils/emailVerificationPrompt";

interface FavoriteEntry {
  id: number;
  ticker: string;
  created_at: string;
}

async function fetchFavorites(): Promise<FavoriteEntry[]> {
  const response = await fetch("/api/auth/favorites/", {
    credentials: "include",
  });
  if (!response.ok) return [];
  return response.json();
}

export function useFavorites() {
  const queryClient = useQueryClient();

  const { data: favorites = [], isLoading } = useQuery({
    queryKey: ["favorites"],
    queryFn: fetchFavorites,
    staleTime: 60 * 1000,
  });

  const addFavorite = useMutation({
    mutationFn: async (ticker: string) => {
      const response = await fetch("/api/auth/favorites/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ ticker }),
      });
      if (!response.ok) throw await buildApiError(response, "Failed to add favorite");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  const removeFavorite = useMutation({
    mutationFn: async (ticker: string) => {
      const response = await fetch(`/api/auth/favorites/${ticker}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfHeaders()["X-CSRFToken"] },
        credentials: "include",
      });
      if (!response.ok) throw await buildApiError(response, "Failed to remove favorite");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  // Memoised because consumers feed this into useMemo/useEffect dependency
  // arrays. A fresh array every render invalidated every one of them, which
  // is how AddFavoriteCard's keyboard highlight ended up being wiped on the
  // render that followed each arrow key.
  const favoriteTickers = useMemo(
    () => favorites.map((favorite) => favorite.ticker),
    [favorites],
  );

  function isFavorite(ticker: string): boolean {
    return favoriteTickers.includes(ticker.toUpperCase());
  }

  function toggleFavorite(ticker: string) {
    const upperTicker = ticker.toUpperCase();
    if (isFavorite(upperTicker)) {
      removeFavorite.mutate(upperTicker);
    } else {
      addFavorite.mutate(upperTicker);
    }
  }

  return {
    favorites,
    favoriteTickers,
    isLoading,
    isFavorite,
    toggleFavorite,
  };
}
