import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";

export interface SavedComparisonEntry {
  id: number;
  name: string;
  tickers: string[];
  years: number;
  share_token: string;
  created_at: string;
  updated_at: string;
}

async function fetchSavedComparisons(): Promise<SavedComparisonEntry[]> {
  const response = await fetch("/api/auth/comparisons/", {
    credentials: "include",
  });
  if (!response.ok) return [];
  return response.json();
}

export function useSavedComparisons() {
  const queryClient = useQueryClient();

  const { data: comparisons = [], isLoading } = useQuery({
    queryKey: ["saved-comparisons"],
    queryFn: fetchSavedComparisons,
    staleTime: 60 * 1000,
  });

  const saveComparison = useMutation({
    mutationFn: async (params: { name: string; tickers: string[]; years: number }) => {
      const response = await fetch("/api/auth/comparisons/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(params),
      });
      if (!response.ok) throw new Error("Failed to save comparison");
      return response.json() as Promise<SavedComparisonEntry>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-comparisons"] });
    },
  });

  const deleteComparison = useMutation({
    mutationFn: async (comparisonId: number) => {
      const response = await fetch(`/api/auth/comparisons/${comparisonId}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfHeaders()["X-CSRFToken"] },
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to delete comparison");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-comparisons"] });
    },
  });

  return {
    comparisons,
    isLoading,
    saveComparison,
    deleteComparison,
  };
}

export interface SharedComparisonData {
  name: string;
  tickers: string[];
  years: number;
  shared_by: string;
  created_at: string;
}

export async function fetchSharedComparison(token: string): Promise<SharedComparisonData> {
  const response = await fetch(`/api/auth/comparisons/shared/${token}/`);
  if (!response.ok) throw new Error("Comparação não encontrada");
  return response.json();
}
