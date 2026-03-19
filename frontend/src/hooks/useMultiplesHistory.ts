import { useQuery } from "@tanstack/react-query";

interface PricePoint {
  date: string;
  adjustedClose: number;
}

interface MultiplePoint {
  year: number;
  value: number | null;
}

interface MultiplesHistoryResult {
  prices: PricePoint[];
  multiples: {
    pl: MultiplePoint[];
    pfcl: MultiplePoint[];
  };
}

async function fetchMultiplesHistory(
  ticker: string,
): Promise<MultiplesHistoryResult> {
  const response = await fetch(`/api/quote/${ticker}/multiples-history/`);

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const fallback =
      response.status === 404
        ? `Ticker "${ticker}" não encontrado.`
        : "Não foi possível obter os dados históricos. Tente novamente mais tarde.";
    throw new Error((data as { error?: string })?.error || fallback);
  }

  return response.json();
}

export type { MultiplesHistoryResult, PricePoint, MultiplePoint };

export function useMultiplesHistory(
  ticker: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["multiples-history", ticker],
    queryFn: () => fetchMultiplesHistory(ticker!),
    enabled: !!ticker && enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
