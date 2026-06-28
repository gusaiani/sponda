import { useQuery, useQueries } from "@tanstack/react-query";

export interface FxSeriesResult {
  from: string;
  to: string;
  rates: { date: string; rate: number }[];
}

export async function fetchFxSeries(
  from: string,
  to: string,
  start?: string,
): Promise<FxSeriesResult> {
  const params = new URLSearchParams({ from, to });
  if (start) params.set("start", start);
  const response = await fetch(`/api/fx/series/?${params.toString()}`);
  if (!response.ok) {
    throw new Error("Não foi possível obter o câmbio histórico.");
  }
  return response.json();
}

/** Historical FX path between two currencies, for the chart's common-currency
 * mode. Disabled (and unfetched) when the currencies match. */
export function useFxSeries(
  from: string | null,
  to: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["fx-series", from, to],
    queryFn: () => fetchFxSeries(from!, to!),
    enabled: enabled && !!from && !!to && from !== to,
    retry: false,
    staleTime: 60 * 60 * 1000,
  });
}

/** FX paths from several source currencies into one target, keyed by source.
 * Same-currency sources map to an empty path (identity). */
export function useFxSeriesMany(
  fromCurrencies: string[],
  to: string | null,
  enabled: boolean,
): Record<string, { date: string; rate: number }[]> {
  const results = useQueries({
    queries: fromCurrencies.map((from) => ({
      queryKey: ["fx-series", from, to],
      queryFn: () => fetchFxSeries(from, to!),
      enabled: enabled && !!to && from !== to,
      retry: false,
      staleTime: 60 * 60 * 1000,
    })),
  });
  const byCurrency: Record<string, { date: string; rate: number }[]> = {};
  fromCurrencies.forEach((from, index) => {
    byCurrency[from] = from === to ? [] : results[index].data?.rates ?? [];
  });
  return byCurrency;
}
