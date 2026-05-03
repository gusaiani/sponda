import { useQuery } from "@tanstack/react-query";

/**
 * Screener row as returned by /api/screener/.
 *
 * Indicator values come back as strings (Django DecimalField serialization) or
 * null. The caller is responsible for parsing to Number when rendering.
 */
export interface ScreenerRow {
  ticker: string;
  name: string;
  sector: string;
  logo: string;
  pe10: string | null;
  pfcf10: string | null;
  peg: string | null;
  pfcf_peg: string | null;
  debt_to_equity: string | null;
  debt_ex_lease_to_equity: string | null;
  liabilities_to_equity: string | null;
  current_ratio: string | null;
  debt_to_avg_earnings: string | null;
  debt_to_avg_fcf: string | null;
  market_cap: number | null;
  current_price: string | null;
}

export interface ScreenerResponse {
  count: number;
  results: ScreenerRow[];
}

/** Numeric indicators the screener can filter on, keyed by model field name. */
export const SCREENER_INDICATORS = [
  "pe10",
  "pfcf10",
  "peg",
  "pfcf_peg",
  "debt_to_equity",
  "debt_ex_lease_to_equity",
  "liabilities_to_equity",
  "current_ratio",
  "debt_to_avg_earnings",
  "debt_to_avg_fcf",
  "market_cap",
] as const;

export type ScreenerIndicator = (typeof SCREENER_INDICATORS)[number];

export interface ScreenerFilters {
  /** Keyed by indicator name; each may set a min, max, or both. */
  bounds: Partial<Record<ScreenerIndicator, { min?: string; max?: string }>>;
  /** Categorical sector filter — empty / undefined means "all sectors". */
  sectors?: string[];
  /** Categorical country filter (ISO alpha-2) — empty / undefined means
   * "all countries". */
  countries?: string[];
  sort: string;
  limit: number;
  offset: number;
}

/**
 * Turn filter state into a query string the backend understands.
 * Empty bounds are dropped so the URL stays tidy and cacheable.
 */
export function buildScreenerQuery(filters: ScreenerFilters): string {
  const params = new URLSearchParams();
  for (const [indicator, bound] of Object.entries(filters.bounds)) {
    if (!bound) continue;
    if (bound.min !== undefined && bound.min !== "") {
      params.set(`${indicator}_min`, bound.min);
    }
    if (bound.max !== undefined && bound.max !== "") {
      params.set(`${indicator}_max`, bound.max);
    }
  }
  if (filters.sectors && filters.sectors.length > 0) {
    params.set("sector", filters.sectors.join(","));
  }
  if (filters.countries && filters.countries.length > 0) {
    params.set("country", filters.countries.join(","));
  }
  params.set("sort", filters.sort);
  params.set("limit", String(filters.limit));
  params.set("offset", String(filters.offset));
  return params.toString();
}

async function fetchScreener(filters: ScreenerFilters): Promise<ScreenerResponse> {
  const query = buildScreenerQuery(filters);
  const response = await fetch(`/api/screener/?${query}`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Screener request failed: ${response.status}`);
  }
  return response.json();
}

export function useScreener(filters: ScreenerFilters) {
  return useQuery({
    queryKey: ["screener", filters],
    queryFn: () => fetchScreener(filters),
    staleTime: 60 * 1000,
  });
}

async function fetchSectors(): Promise<string[]> {
  const response = await fetch("/api/screener/sectors/", {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Sectors request failed: ${response.status}`);
  }
  const body: { sectors: string[] } = await response.json();
  return body.sectors;
}

/** Distinct sector list for populating the sector multi-select. The list
 * rarely changes, so it stays warm for an hour to avoid refetching on
 * every screener interaction. */
export function useScreenerSectors() {
  return useQuery({
    queryKey: ["screener-sectors"],
    queryFn: fetchSectors,
    staleTime: 60 * 60 * 1000,
  });
}

async function fetchCountries(): Promise<string[]> {
  const response = await fetch("/api/screener/countries/", {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`Countries request failed: ${response.status}`);
  }
  const body: { countries: string[] } = await response.json();
  return body.countries;
}

export function useScreenerCountries() {
  return useQuery({
    queryKey: ["screener-countries"],
    queryFn: fetchCountries,
    staleTime: 60 * 60 * 1000,
  });
}
