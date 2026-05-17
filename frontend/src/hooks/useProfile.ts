import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";

export interface PublicUser {
  handle: string;
  display_name: string;
  bio: string;
  is_private: boolean;
}

export interface PublicProfile {
  user: PublicUser;
  follower_count: number;
  following_count: number;
  viewer_is_following: false | "pending" | "accepted";
  sponds: SpondPayload[];
}

export interface SpondPayload {
  id: string;
  author: PublicUser;
  body: string;
  ticker: string;
  parent: string | null;
  created_at: string;
  updated_at: string;
  is_within_edit_window: boolean;
  like_count: number;
  reply_count: number;
  viewer_has_liked: boolean;
  ticker_mentions: string[];
  handle_mentions: string[];
}

export interface ProfileUpdatePayload {
  handle?: string;
  display_name?: string;
  bio?: string;
  is_private?: boolean;
}

async function fetchProfile(handle: string): Promise<PublicProfile | null> {
  const r = await fetch(`/api/social/users/${handle}/`, {
    credentials: "include",
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("profile_fetch_failed");
  return r.json();
}

async function patchProfile(payload: ProfileUpdatePayload): Promise<PublicUser> {
  const r = await fetch("/api/social/users/me/profile/", {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...csrfHeaders(),
    },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    const error = new Error(detail.detail || "profile_update_failed");
    (error as Error & { detail?: unknown }).detail = detail;
    throw error;
  }
  return r.json();
}

export function useProfile(handle: string | null | undefined) {
  return useQuery({
    queryKey: ["social-profile", handle],
    queryFn: () => fetchProfile(handle as string),
    enabled: !!handle,
    staleTime: 30_000,
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchProfile,
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: ["auth-user"] });
      queryClient.invalidateQueries({ queryKey: ["social-profile", user.handle] });
    },
  });
}
