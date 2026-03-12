import { useQuery } from "@tanstack/react-query";

interface QuotaResult {
  limit: number;
  used: number;
  remaining: number;
  authenticated: boolean;
}

async function fetchQuota(): Promise<QuotaResult> {
  const response = await fetch("/api/auth/quota/", {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch quota");
  }
  return response.json();
}

export function useQuota() {
  return useQuery({
    queryKey: ["quota"],
    queryFn: fetchQuota,
    staleTime: 30 * 1000,
  });
}
