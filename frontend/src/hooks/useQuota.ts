import { useQuery } from "@tanstack/react-query";
import type { LookupScope } from "./usePE10";

export interface QuotaResult {
  /** null = unlimited (email-verified users). */
  limit: number | null;
  used: number;
  /** null = unlimited. 0 = cap exhausted. */
  remaining: number | null;
  authenticated: boolean;
  email_verified: boolean;
  scope: LookupScope;
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

/** Show the cap banner only when the limit is finite AND fully spent.
 *  Unlimited users (remaining === null) and users with headroom must
 *  never see it. */
export function shouldShowQuotaAlert(data: QuotaResult | undefined): boolean {
  if (!data) return false;
  if (data.remaining === null) return false;
  return data.remaining <= 0;
}

export function useQuota() {
  return useQuery({
    queryKey: ["quota"],
    queryFn: fetchQuota,
    staleTime: 30 * 1000,
  });
}
