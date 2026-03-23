import { useQuery } from "@tanstack/react-query";

export interface FundamentalsYear {
  year: number;
  quarters: number;
  balanceSheetDate: string | null;
  // Balance sheet
  totalDebt: number | null;
  totalLease: number | null;
  debtExLease: number | null;
  totalLiabilities: number | null;
  stockholdersEquity: number | null;
  currentAssets: number | null;
  currentLiabilities: number | null;
  // Ratios
  debtToEquity: number | null;
  liabilitiesToEquity: number | null;
  currentRatio: number | null;
  // Income
  revenue: number | null;
  revenueAdjusted: number | null;
  netIncome: number | null;
  netIncomeAdjusted: number | null;
  // Cash flow
  fcf: number | null;
  fcfAdjusted: number | null;
  operatingCashFlow: number | null;
  operatingCashFlowAdjusted: number | null;
  dividendsPaid: number | null;
  dividendsAdjusted: number | null;
  // IPCA
  ipcaFactor: number;
}

async function fetchFundamentals(ticker: string): Promise<FundamentalsYear[]> {
  const response = await fetch(`/api/quote/${ticker}/fundamentals/`, {
    credentials: "include",
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const fallback =
      response.status === 404
        ? `Ticker "${ticker}" não encontrado.`
        : "Não foi possível obter os dados no momento.";
    throw new Error(data?.error || fallback);
  }

  return response.json();
}

export function useFundamentals(ticker: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["fundamentals", ticker],
    queryFn: () => fetchFundamentals(ticker!),
    enabled: !!ticker && enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
