import { djangoApiBaseUrl } from "../../../lib/django-api";
import type { Peer } from "../../../hooks/usePeers";

const PEERS_REVALIDATE_SECONDS = 3600;

function isPeer(value: unknown): value is Peer {
  return typeof value === "object" && value !== null
    && typeof (value as Peer).symbol === "string";
}

/**
 * Same-sector peers, fetched on the server so their links are in the first
 * HTML. Before this, the peers arrived from the browser, so a crawler that
 * did not run JavaScript saw one company page link to nothing but its own
 * tabs, and the home page was the only way in to any of them.
 *
 * Anonymous and cached: the endpoint is public and Django caches it for an
 * hour itself. Never throws; a page without peers still beats no page.
 */
export async function fetchPeersServer(ticker: string): Promise<Peer[]> {
  try {
    const response = await fetch(`${djangoApiBaseUrl()}/api/tickers/${ticker}/peers/`, {
      next: { revalidate: PEERS_REVALIDATE_SECONDS },
    });
    if (!response.ok) return [];
    const payload: unknown = await response.json();
    if (!Array.isArray(payload)) return [];
    return payload.filter(isPeer);
  } catch {
    return [];
  }
}
