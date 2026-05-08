import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";

export type FollowState = false | "pending" | "accepted";

interface FollowResponse {
  state: "pending" | "accepted";
}

async function postFollow(handle: string, follow: boolean): Promise<FollowResponse | void> {
  const r = await fetch(`/api/social/users/${handle}/follow/`, {
    method: follow ? "POST" : "DELETE",
    credentials: "include",
    headers: csrfHeaders(),
  });
  if (!r.ok && r.status !== 204) throw new Error("follow_failed");
  if (r.status === 204) return undefined;
  return r.json();
}

export function useToggleFollow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ handle, follow }: { handle: string; follow: boolean }) =>
      postFollow(handle, follow),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["social-profile", vars.handle] });
      queryClient.invalidateQueries({ queryKey: ["social-feed"] });
    },
  });
}

interface FollowRequest {
  id: number;
  follower: { handle: string; display_name: string; bio: string; is_private: boolean };
  state: "pending" | "accepted";
  created_at: string;
}

async function fetchFollowRequests(): Promise<FollowRequest[]> {
  const r = await fetch("/api/social/users/me/follow-requests/", {
    credentials: "include",
  });
  if (!r.ok) throw new Error("follow_requests_fetch_failed");
  return r.json();
}

async function actOnRequest(id: number, action: "accept" | "reject"): Promise<void> {
  const r = await fetch(`/api/social/follow-requests/${id}/${action}/`, {
    method: "POST",
    credentials: "include",
    headers: csrfHeaders(),
  });
  if (!r.ok && r.status !== 204) throw new Error("follow_request_action_failed");
}

export function useFollowRequests() {
  return useQuery({
    queryKey: ["follow-requests"],
    queryFn: fetchFollowRequests,
    staleTime: 30_000,
  });
}

export function useFollowRequestAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: "accept" | "reject" }) =>
      actOnRequest(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-requests"] });
      queryClient.invalidateQueries({ queryKey: ["social-notifications"] });
    },
  });
}
