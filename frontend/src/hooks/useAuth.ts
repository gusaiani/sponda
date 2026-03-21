import { useQuery, useQueryClient } from "@tanstack/react-query";

export interface AuthUser {
  email: string;
  is_superuser: boolean;
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
      credentials: "include",
    });
    queryClient.setQueryData(["auth-user"], null);
    queryClient.invalidateQueries({ queryKey: ["quota"] });
  }

  return {
    user: user ?? null,
    isAuthenticated: !!user,
    isSuperuser: user?.is_superuser ?? false,
    isLoading,
    logout,
  };
}
