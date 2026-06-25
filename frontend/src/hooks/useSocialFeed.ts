import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";
import type { SpondPayload } from "./useProfile";

export type FeedKind = "following" | "global" | "company";

export interface FeedPage {
  results: SpondPayload[];
  next: string | null;
  previous: string | null;
}

function endpointFor(kind: FeedKind, ticker?: string): string {
  if (kind === "following") return "/api/social/feed/";
  if (kind === "global") return "/api/social/feed/global/";
  if (kind === "company") {
    if (!ticker) throw new Error("ticker required for company feed");
    return `/api/social/companies/${ticker}/sponds/`;
  }
  throw new Error(`unknown feed kind: ${kind}`);
}

async function fetchFeedPage(url: string): Promise<FeedPage> {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error("feed_fetch_failed");
  return r.json();
}

export function useSocialFeed(kind: FeedKind, ticker?: string) {
  return useInfiniteQuery({
    queryKey: ["social-feed", kind, ticker ?? null],
    initialPageParam: endpointFor(kind, ticker),
    queryFn: ({ pageParam }) => fetchFeedPage(pageParam as string),
    getNextPageParam: (lastPage) => lastPage.next,
  });
}

interface CreateSpondInput {
  body: string;
  ticker?: string;
  parent?: string;
}

async function postSpond(input: CreateSpondInput): Promise<SpondPayload> {
  const r = await fetch("/api/social/sponds/", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(input),
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    const error = new Error(detail.detail || "spond_create_failed");
    (error as Error & { detail?: unknown; status?: number }).detail = detail;
    (error as Error & { detail?: unknown; status?: number }).status = r.status;
    throw error;
  }
  return r.json();
}

export function useCreateSpond() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: postSpond,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["social-feed"] });
      queryClient.invalidateQueries({ queryKey: ["social-profile"] });
      // Refresh any already-expanded thread so an inline reply shows up
      // immediately under its parent in the feed.
      queryClient.invalidateQueries({ queryKey: ["social-thread"] });
    },
  });
}

async function postLike(spondId: string, like: boolean): Promise<void> {
  const r = await fetch(`/api/social/sponds/${spondId}/like/`, {
    method: like ? "POST" : "DELETE",
    credentials: "include",
    headers: csrfHeaders(),
  });
  if (!r.ok) throw new Error("like_failed");
}

export function useLikeSpond() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, like }: { id: string; like: boolean }) =>
      postLike(id, like),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["social-feed"] });
      queryClient.invalidateQueries({ queryKey: ["social-profile"] });
    },
  });
}

async function deleteSpondRequest(id: string): Promise<void> {
  const r = await fetch(`/api/social/sponds/${id}/`, {
    method: "DELETE",
    credentials: "include",
    headers: csrfHeaders(),
  });
  if (!r.ok && r.status !== 204) throw new Error("delete_failed");
}

export function useDeleteSpond() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteSpondRequest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["social-feed"] });
      queryClient.invalidateQueries({ queryKey: ["social-profile"] });
    },
  });
}
