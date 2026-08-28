import { useQuery } from "@tanstack/react-query";

export interface Peer {
  symbol: string;
  name: string;
}

const PEERS_STALE_TIME_MS = 60 * 60 * 1000;

async function fetchPeers(symbol: string): Promise<Peer[]> {
  const response = await fetch(`/api/tickers/${symbol}/peers/`, { credentials: "include" });
  if (!response.ok) return [];
  return response.json();
}

/**
 * Same-sector peers of a company.
 *
 * `initialPeers` is what the server already rendered. Seeding the query
 * with it keeps the peer links in the first HTML (they are the only
 * internal links from one company page to another) and spares the browser
 * a round trip. An empty list is not a seed: the server helper answers []
 * on any failure, and pinning that for an hour would hide the peers.
 */
export function usePeers(symbol: string, initialPeers?: Peer[]) {
  const hasServerPeers = initialPeers !== undefined && initialPeers.length > 0;
  return useQuery({
    queryKey: ["peers", symbol],
    queryFn: () => fetchPeers(symbol),
    staleTime: PEERS_STALE_TIME_MS,
    enabled: !!symbol,
    initialData: hasServerPeers ? initialPeers : undefined,
  });
}
