import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";
import type { ScreenerFilters } from "./useScreener";

export interface SavedScreenerFilterEntry {
  id: number;
  name: string;
  bounds: ScreenerFilters["bounds"];
  sort: string;
  created_at: string;
  updated_at: string;
}

async function fetchSavedScreenerFilters(): Promise<SavedScreenerFilterEntry[]> {
  const response = await fetch("/api/auth/screener-filters/", {
    credentials: "include",
  });
  if (!response.ok) return [];
  return response.json();
}

export function useSavedScreenerFilters() {
  const queryClient = useQueryClient();

  const { data: filters = [], isLoading } = useQuery({
    queryKey: ["saved-screener-filters"],
    queryFn: fetchSavedScreenerFilters,
    staleTime: 60 * 1000,
  });

  const saveFilter = useMutation({
    mutationFn: async (params: {
      name: string;
      bounds: ScreenerFilters["bounds"];
      sort: string;
    }) => {
      const response = await fetch("/api/auth/screener-filters/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(params),
      });
      if (!response.ok) throw new Error("Failed to save filter");
      return response.json() as Promise<SavedScreenerFilterEntry>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-screener-filters"] });
    },
  });

  const updateFilter = useMutation({
    mutationFn: async (params: {
      id: number;
      name?: string;
      bounds?: ScreenerFilters["bounds"];
      sort?: string;
    }) => {
      const { id, ...body } = params;
      const response = await fetch(`/api/auth/screener-filters/${id}/`, {
        method: "PUT",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error("Failed to update filter");
      return response.json() as Promise<SavedScreenerFilterEntry>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-screener-filters"] });
    },
  });

  const deleteFilter = useMutation({
    mutationFn: async (filterId: number) => {
      const response = await fetch(`/api/auth/screener-filters/${filterId}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfHeaders()["X-CSRFToken"] },
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to delete filter");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-screener-filters"] });
    },
  });

  return {
    filters,
    isLoading,
    saveFilter,
    updateFilter,
    deleteFilter,
  };
}
