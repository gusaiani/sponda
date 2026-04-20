import { useQuery, useQueryClient } from "@tanstack/react-query";
import { csrfHeaders } from "../utils/csrf";

export interface AuthUser {
  email: string;
  is_superuser: boolean;
  email_verified: boolean;
  date_joined: string;
  allow_contact: boolean;
}

async function fetchMe(): Promise<AuthUser | null> {
  const response = await fetch("/api/auth/me/", {
    credentials: "include",
  });
  if (!response.ok) return null;
  return response.json();
}

export function useAuth() {
  const queryClient = useQueryClient();

  const { data: user, isLoading } = useQuery({
    queryKey: ["auth-user"],
    queryFn: fetchMe,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  async function logout() {
    await fetch("/api/auth/logout/", {
      method: "POST",
      headers: { "X-CSRFToken": csrfHeaders()["X-CSRFToken"] },
      credentials: "include",
    });
    queryClient.setQueryData(["auth-user"], null);
    queryClient.invalidateQueries({ queryKey: ["quota"] });
  }

  async function refreshUser() {
    await queryClient.invalidateQueries({ queryKey: ["auth-user"] });
  }

  return {
    user: user ?? null,
    isAuthenticated: !!user,
    isSuperuser: user?.is_superuser ?? false,
    isLoading,
    logout,
    refreshUser,
  };
}
