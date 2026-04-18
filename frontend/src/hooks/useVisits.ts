import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";
import { localToday } from "../utils/format";

export interface VisitEntry {
  id: number;
  ticker: string;
  visited_at: string;
  note: string;
  created_at: string;
}

export interface RevisitScheduleEntry {
  id: number;
  ticker: string;
  next_revisit: string;
  recurrence_days: number | null;
  share_token: string;
  notified_at: string | null;
  created_at: string;
  updated_at: string;
}

interface MarkVisitedPayload {
  ticker: string;
  note?: string;
  next_revisit?: string;
  recurrence_days?: number;
}

interface MarkVisitedResult {
  visit: VisitEntry;
  schedule: RevisitScheduleEntry | null;
}

interface PendingReminders {
  count: number;
  schedules: RevisitScheduleEntry[];
}

async function fetchVisits(ticker?: string): Promise<VisitEntry[]> {
  const url = ticker ? `/api/auth/visits/?ticker=${ticker}` : "/api/auth/visits/";
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) return [];
  return response.json();
}

async function fetchSchedules(): Promise<RevisitScheduleEntry[]> {
  const response = await fetch("/api/auth/visits/schedules/", { credentials: "include" });
  if (!response.ok) return [];
  return response.json();
}

async function fetchReminders(): Promise<PendingReminders> {
  const response = await fetch("/api/auth/visits/reminders/", { credentials: "include" });
  if (!response.ok) return { count: 0, schedules: [] };
  return response.json();
}

export function useVisits(ticker?: string) {
  const queryClient = useQueryClient();

  const { data: visits = [], isLoading } = useQuery({
    queryKey: ticker ? ["visits", ticker] : ["visits"],
    queryFn: () => fetchVisits(ticker),
    staleTime: 60 * 1000,
  });

  const markVisited = useMutation({
    mutationFn: async (payload: MarkVisitedPayload): Promise<MarkVisitedResult> => {
      const response = await fetch("/api/auth/visits/mark/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("Failed to mark visited");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["visits"] });
      queryClient.invalidateQueries({ queryKey: ["revisit-schedules"] });
      queryClient.invalidateQueries({ queryKey: ["pending-reminders"] });
    },
  });

  function isVisitedToday(checkTicker: string): boolean {
    const today = localToday();
    return visits.some(
      (visit) => visit.ticker === checkTicker.toUpperCase() && visit.visited_at === today,
    );
  }

  return { visits, isLoading, markVisited, isVisitedToday };
}

export function useRevisitSchedules() {
  const queryClient = useQueryClient();

  const { data: schedules = [], isLoading } = useQuery({
    queryKey: ["revisit-schedules"],
    queryFn: fetchSchedules,
    staleTime: 60 * 1000,
  });

  const updateSchedule = useMutation({
    mutationFn: async ({ id, ...data }: { id: number; next_revisit?: string; recurrence_days?: number | null }) => {
      const response = await fetch(`/api/auth/visits/schedules/${id}/`, {
        method: "PUT",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error("Failed to update schedule");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["revisit-schedules"] });
      queryClient.invalidateQueries({ queryKey: ["pending-reminders"] });
    },
  });

  const deleteSchedule = useMutation({
    mutationFn: async (id: number) => {
      const response = await fetch(`/api/auth/visits/schedules/${id}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": csrfHeaders()["X-CSRFToken"] },
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to delete schedule");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["revisit-schedules"] });
      queryClient.invalidateQueries({ queryKey: ["pending-reminders"] });
    },
  });

  function getScheduleForTicker(ticker: string): RevisitScheduleEntry | undefined {
    return schedules.find((schedule) => schedule.ticker === ticker.toUpperCase());
  }

  return { schedules, isLoading, updateSchedule, deleteSchedule, getScheduleForTicker };
}

export function usePendingReminders() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["pending-reminders"],
    queryFn: fetchReminders,
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });

  const dismissReminder = useMutation({
    mutationFn: async (id: number) => {
      const response = await fetch(`/api/auth/visits/reminders/${id}/dismiss/`, {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to dismiss reminder");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-reminders"] });
      queryClient.invalidateQueries({ queryKey: ["reminders-list"] });
      queryClient.invalidateQueries({ queryKey: ["revisit-schedules"] });
    },
  });

  const dismissAllReminders = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/auth/visits/reminders/dismiss-all/", {
        method: "POST",
        headers: csrfHeaders(),
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to dismiss reminders");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-reminders"] });
      queryClient.invalidateQueries({ queryKey: ["reminders-list"] });
      queryClient.invalidateQueries({ queryKey: ["revisit-schedules"] });
    },
  });

  return {
    count: data?.count ?? 0,
    schedules: data?.schedules ?? [],
    isLoading,
    dismissReminder,
    dismissAllReminders,
  };
}

interface RemindersListResponse {
  count: number;
  page: number;
  page_size: number;
  schedules: RevisitScheduleEntry[];
}

async function fetchRemindersList(page: number): Promise<RemindersListResponse> {
  const response = await fetch(`/api/auth/visits/reminders/list/?page=${page}`, {
    credentials: "include",
  });
  if (!response.ok) return { count: 0, page, page_size: 30, schedules: [] };
  return response.json();
}

export function useRemindersList(page: number) {
  return useQuery({
    queryKey: ["reminders-list", page],
    queryFn: () => fetchRemindersList(page),
    staleTime: 60 * 1000,
  });
}
