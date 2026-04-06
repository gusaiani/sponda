import { useQuery } from "@tanstack/react-query";

interface TickerDetail {
  symbol: string;
  name: string;
  sector: string;
  type: string;
  logo: string;
}

async function fetchTickerDetail(symbol: string): Promise<TickerDetail | null> {
  const response = await fetch(`/api/tickers/${symbol}/`, { credentials: "include" });
  if (!response.ok) return null;
  return response.json();
}

export function useTickerDetail(symbol: string) {
  return useQuery({
    queryKey: ["tickerDetail", symbol],
    queryFn: () => fetchTickerDetail(symbol),
    staleTime: 60 * 60 * 1000,
    enabled: !!symbol,
  });
}
