import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders, getCSRFToken } from "../utils/csrf";

/**
 * Indicator alert as returned by /api/auth/alerts/.
 *
 * `threshold` comes back as a string (Django DecimalField serialization).
 * The comparison is either "lte" (triggers when value <= threshold, e.g. PE10
 * dropped to a buying level) or "gte" (triggers when value >= threshold, e.g.
 * leverage rose above a worry line).
 */
export interface IndicatorAlert {
  id: number;
  ticker: string;
  indicator: string;
  comparison: "lte" | "gte";
  threshold: string;
  active: boolean;
  triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateAlertPayload {
  ticker: string;
  indicator: string;
  comparison: "lte" | "gte";
  threshold: string;
}

export interface UpdateAlertPayload {
  active?: boolean;
  threshold?: string;
  comparison?: "lte" | "gte";
}

/**
 * Build the alerts list URL. Keeping this as a pure function (rather than
 * inlining the conditional) makes the ticker-filter behavior unit-testable
 * without mocking fetch.
 */
export function buildAlertsListUrl(ticker?: string): string {
  return ticker
    ? `/api/auth/alerts/?ticker=${encodeURIComponent(ticker.toUpperCase())}`
    : "/api/auth/alerts/";
}

async function fetchAlerts(ticker?: string): Promise<IndicatorAlert[]> {
  const response = await fetch(buildAlertsListUrl(ticker), {
    credentials: "include",
  });
  if (!response.ok) return [];
  return response.json();
}

/**
 * React Query hook for reading + mutating alerts.
 * Pass a `ticker` to scope the list query (the mutations still invalidate
 * the full "alerts" key space so any other subscribers refresh too).
 */
export function useAlerts(ticker?: string) {
  const queryClient = useQueryClient();
  const normalizedTicker = ticker ? ticker.toUpperCase() : undefined;

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: normalizedTicker ? ["alerts", normalizedTicker] : ["alerts"],
    queryFn: () => fetchAlerts(normalizedTicker),
    staleTime: 60 * 1000,
  });

  const createAlert = useMutation({
    mutationFn: async (payload: CreateAlertPayload): Promise<IndicatorAlert> => {
      const response = await fetch("/api/auth/alerts/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Failed to create alert (${response.status})`);
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  const updateAlert = useMutation({
    mutationFn: async ({
      id,
      ...changes
    }: UpdateAlertPayload & { id: number }): Promise<IndicatorAlert> => {
      const response = await fetch(`/api/auth/alerts/${id}/`, {
        method: "PATCH",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(changes),
      });
      if (!response.ok) {
        throw new Error(`Failed to update alert (${response.status})`);
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  const deleteAlert = useMutation({
    mutationFn: async (id: number): Promise<void> => {
      const response = await fetch(`/api/auth/alerts/${id}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCSRFToken() },
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(`Failed to delete alert (${response.status})`);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  return { alerts, isLoading, createAlert, updateAlert, deleteAlert };
}
