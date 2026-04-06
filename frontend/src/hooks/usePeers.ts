import { useQuery } from "@tanstack/react-query";

interface Peer {
  symbol: string;
  name: string;
}

async function fetchPeers(symbol: string): Promise<Peer[]> {
  const response = await fetch(`/api/tickers/${symbol}/peers/`, { credentials: "include" });
  if (!response.ok) return [];
  return response.json();
}

export function usePeers(symbol: string) {
  return useQuery({
    queryKey: ["peers", symbol],
    queryFn: () => fetchPeers(symbol),
    staleTime: 60 * 60 * 1000,
    enabled: !!symbol,
  });
}
