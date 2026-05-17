import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";

export interface SocialNotification {
  id: number;
  verb: "followed" | "follow_requested" | "replied" | "mentioned" | "liked";
  actor: { handle: string; display_name: string; bio: string; is_private: boolean } | null;
  target_type: string | null;
  target_id: string | null;
  read_at: string | null;
  created_at: string;
}

interface NotificationsResponse {
  unread_count: number;
  notifications: SocialNotification[];
}

async function fetchNotifications(): Promise<NotificationsResponse> {
  const r = await fetch("/api/social/notifications/", { credentials: "include" });
  if (!r.ok) throw new Error("notifications_fetch_failed");
  return r.json();
}

async function postMarkRead(ids?: number[]): Promise<void> {
  const r = await fetch("/api/social/notifications/mark-read/", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(ids ? { ids } : {}),
  });
  if (!r.ok) throw new Error("mark_read_failed");
}

export function useSocialNotifications(enabled: boolean) {
  return useQuery({
    queryKey: ["social-notifications"],
    queryFn: fetchNotifications,
    enabled,
    refetchInterval: 60_000,
  });
}

export function useMarkNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids?: number[]) => postMarkRead(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["social-notifications"] });
    },
  });
}
