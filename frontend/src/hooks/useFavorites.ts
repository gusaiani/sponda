import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

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
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ ticker }),
      });
      if (!response.ok) throw new Error("Failed to add favorite");
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
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to remove favorite");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  const favoriteTickers = favorites.map((favorite) => favorite.ticker);

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
