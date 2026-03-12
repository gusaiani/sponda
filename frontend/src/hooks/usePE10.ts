import { useQuery } from "@tanstack/react-query";

interface PE10Result {
  ticker: string;
  name: string;
  pe10: number | null;
  currentPrice: number;
  avgAdjustedEPS: number | null;
  yearsOfData: number;
  label: string;
  error: string | null;
}

interface PE10Error {
  error: string;
  limit?: number;
  used?: number;
}

async function fetchPE10(ticker: string): Promise<PE10Result> {
  const response = await fetch(`/api/quote/${ticker}/`, {
    credentials: "include",
  });

  if (response.status === 403) {
    const data: PE10Error = await response.json();
    throw new Error(data.error);
  }

  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.error || "Failed to fetch PE10 data");
  }

  return response.json();
}

export function usePE10(ticker: string | null) {
  return useQuery({
    queryKey: ["pe10", ticker],
    queryFn: () => fetchPE10(ticker!),
    enabled: !!ticker,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
