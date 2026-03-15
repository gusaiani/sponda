import { useQuery } from "@tanstack/react-query";

interface QuarterlyEarningsDetail {
  end_date: string;
  net_income: number;
}

interface PE10YearlyBreakdown {
  year: number;
  nominalNetIncome: number;
  ipcaFactor: number;
  adjustedNetIncome: number;
  quarters: number;
  quarterlyDetail: QuarterlyEarningsDetail[];
}

interface QuarterlyCFDetail {
  end_date: string;
  operating_cash_flow: number;
  investment_cash_flow: number;
  fcf: number;
}

interface PFCF10YearlyBreakdown {
  year: number;
  nominalFCF: number;
  ipcaFactor: number;
  adjustedFCF: number;
  quarters: number;
  quarterlyDetail: QuarterlyCFDetail[];
}

interface QuoteResult {
  ticker: string;
  name: string;
  logo: string;
  currentPrice: number;
  marketCap: number | null;
  // PE10
  pe10: number | null;
  avgAdjustedNetIncome: number | null;
  pe10YearsOfData: number;
  pe10Label: string;
  pe10Error: string | null;
  pe10AnnualData: boolean;
  pe10CalculationDetails: PE10YearlyBreakdown[];
  // PFCF10
  pfcf10: number | null;
  avgAdjustedFCF: number | null;
  pfcf10YearsOfData: number;
  pfcf10Label: string;
  pfcf10Error: string | null;
  pfcf10AnnualData: boolean;
  pfcf10CalculationDetails: PFCF10YearlyBreakdown[];
  // Leverage
  debtToEquity: number | null;
  liabilitiesToEquity: number | null;
  leverageError: string | null;
  leverageDate: string | null;
  totalDebt: number | null;
  totalLiabilities: number | null;
  stockholdersEquity: number | null;
  // Debt coverage
  debtToAvgEarnings: number | null;
  debtToAvgFCF: number | null;
}

interface QuoteError {
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

async function fetchQuote(ticker: string): Promise<QuoteResult> {
  const response = await fetch(`/api/quote/${ticker}/`, {
    credentials: "include",
  });

  if (!response.ok) {
    const data = (await parseJSON(response)) as QuoteError | null;
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
    queryFn: () => fetchQuote(ticker!),
    enabled: !!ticker,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
