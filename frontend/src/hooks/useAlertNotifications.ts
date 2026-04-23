import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";
import { buildApiError } from "../utils/emailVerificationPrompt";

export interface AlertNotificationEntry {
  id: number;
  ticker: string;
  indicator: string;
  comparison: "lte" | "gte";
  threshold: string;
  indicator_value: string | null;
  dismissed_at: string | null;
  created_at: string;
}

interface AlertNotificationsResponse {
  count: number;
  notifications: AlertNotificationEntry[];
}

async function fetchAlertNotifications(): Promise<AlertNotificationsResponse> {
  const response = await fetch("/api/auth/alert-notifications/", {
    credentials: "include",
  });
  if (!response.ok) return { count: 0, notifications: [] };
  return response.json();
}

export function useAlertNotifications() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["alert-notifications"],
    queryFn: fetchAlertNotifications,
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });

  const dismissNotification = useMutation({
    mutationFn: async (id: number) => {
      const response = await fetch(`/api/auth/alert-notifications/${id}/dismiss/`, {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
      });
      if (!response.ok) throw await buildApiError(response, "Failed to dismiss notification");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert-notifications"] });
    },
  });

  const dismissAllNotifications = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/auth/alert-notifications/dismiss-all/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
      });
      if (!response.ok) throw await buildApiError(response, "Failed to dismiss notifications");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert-notifications"] });
    },
  });

  return {
    count: data?.count ?? 0,
    notifications: data?.notifications ?? [],
    isLoading,
    dismissNotification,
    dismissAllNotifications,
  };
}
