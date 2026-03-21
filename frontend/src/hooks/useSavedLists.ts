import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";

export interface SavedListEntry {
  id: number;
  name: string;
  tickers: string[];
  years: number;
  share_token: string;
  created_at: string;
  updated_at: string;
}

async function fetchSavedLists(): Promise<SavedListEntry[]> {
  const response = await fetch("/api/auth/lists/", {
    credentials: "include",
  });
  if (!response.ok) return [];
  return response.json();
}

export function useSavedLists() {
  const queryClient = useQueryClient();

  const { data: lists = [], isLoading } = useQuery({
    queryKey: ["saved-lists"],
    queryFn: fetchSavedLists,
    staleTime: 60 * 1000,
  });

  const saveList = useMutation({
    mutationFn: async (params: { name: string; tickers: string[]; years: number }) => {
      const response = await fetch("/api/auth/lists/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(params),
      });
      if (!response.ok) throw new Error("Failed to save list");
      return response.json() as Promise<SavedListEntry>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-lists"] });
    },
  });

  const updateList = useMutation({
    mutationFn: async (params: { id: number; tickers?: string[]; years?: number; name?: string }) => {
      const { id, ...body } = params;
      const response = await fetch(`/api/auth/lists/${id}/`, {
        method: "PUT",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error("Failed to update list");
      return response.json() as Promise<SavedListEntry>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-lists"] });
    },
  });

  const deleteList = useMutation({
    mutationFn: async (listId: number) => {
      const response = await fetch(`/api/auth/lists/${listId}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfHeaders()["X-CSRFToken"] },
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to delete list");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-lists"] });
    },
  });

  const reorderLists = useMutation({
    mutationFn: async (orderedIds: number[]) => {
      const response = await fetch("/api/auth/lists/reorder/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ ordered_ids: orderedIds }),
      });
      if (!response.ok) throw new Error("Failed to reorder lists");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-lists"] });
    },
  });

  return {
    lists,
    isLoading,
    saveList,
    updateList,
    deleteList,
    reorderLists,
  };
}

export interface SharedListData {
  name: string;
  tickers: string[];
  years: number;
  shared_by: string;
  created_at: string;
}

export async function fetchSharedList(token: string): Promise<SharedListData> {
  const response = await fetch(`/api/auth/lists/shared/${token}/`);
  if (!response.ok) throw new Error("Lista não encontrada");
  return response.json();
}
