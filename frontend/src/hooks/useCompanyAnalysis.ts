import { useQuery } from "@tanstack/react-query";

export interface AnalysisVersion {
  id: number;
  dataQuarter: string;
  generatedAt: string;
}

export interface CompanyAnalysisResult {
  ticker: string;
  content: string;
  dataQuarter: string;
  generatedAt: string;
  versions: AnalysisVersion[];
}

async function fetchCompanyAnalysis(ticker: string): Promise<CompanyAnalysisResult> {
  const response = await fetch(`/api/quote/${ticker}/analysis/`, {
    credentials: "include",
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error || "Análise indisponível.");
  }

  return response.json();
}

export function useCompanyAnalysis(ticker: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["company-analysis", ticker],
    queryFn: () => fetchCompanyAnalysis(ticker!),
    enabled: !!ticker && enabled,
    retry: false,
    staleTime: 10 * 60 * 1000,
  });
}
