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
  annualData: boolean;
}

interface PE10Error {
  error: string;
  limit?: number;
  used?: number;
}

async function parseJSON(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function fetchPE10(ticker: string): Promise<PE10Result> {
  const response = await fetch(`/api/quote/${ticker}/`, {
    credentials: "include",
  });

  if (!response.ok) {
    const data = (await parseJSON(response)) as PE10Error | null;
    const fallback =
      response.status === 404
        ? `Ticker "${ticker}" não encontrado. Verifique o código e tente novamente.`
        : "Não foi possível obter os dados no momento. Tente novamente mais tarde.";
    throw new Error(data?.error || fallback);
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
