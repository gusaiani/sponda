import { useQuery } from "@tanstack/react-query";

export interface TickerItem {
  symbol: string;
  name: string;
  sector: string;
  type: string;
  logo: string;
}

async function fetchTickers(): Promise<TickerItem[]> {
  const response = await fetch("/api/tickers/", { credentials: "include" });
  if (!response.ok) throw new Error("Failed to fetch tickers");
  return response.json();
}

export function useTickers() {
  return useQuery({
    queryKey: ["tickers"],
    queryFn: fetchTickers,
    staleTime: 60 * 60 * 1000,
  });
}
