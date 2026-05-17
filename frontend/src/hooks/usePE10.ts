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
  /** Market cap translated into the reporting currency (USD × USDDKK for
   * NVO, etc.). Used by the slider-driven PE/PFCF recompute on the
   * frontend. Null when FX is unavailable. */
  marketCapInReportedCurrency?: number | null;
  /** ISO 4217 of the currency the quote/marketCap is denominated in (USD or BRL).
   * Optional only because legacy fixtures may omit it. */
  listingCurrency?: string;
  /** ISO 4217 of the currency the company files financials in (USD, BRL, DKK,
   * EUR, JPY, ...). When this differs from listingCurrency, market-cap-based
   * indicators are translated server-side via the FX rate. */
  reportedCurrency?: string;
  maxYearsAvailable: number;
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
  debtExLeaseToEquity: number | null;
  liabilitiesToEquity: number | null;
  currentRatio: number | null;
  leverageError: string | null;
  leverageDate: string | null;
  totalDebt: number | null;
  totalLease: number | null;
  totalLiabilities: number | null;
  stockholdersEquity: number | null;
  // Debt coverage
  debtToAvgEarnings: number | null;
  debtToAvgFCF: number | null;
  // PEG
  peg: number | null;
  earningsCAGR: number | null;
  pegError: string | null;
  earningsCAGRMethod: "endpoint" | "regression" | null;
  earningsCAGRExcludedYears: number[];
  // PFCLG
  pfcfPeg: number | null;
  fcfCAGR: number | null;
  pfcfPegError: string | null;
  fcfCAGRMethod: "endpoint" | "regression" | null;
  fcfCAGRExcludedYears: number[];
  // Profitability (computed client-side)
  roe: number | null;
  priceToBook: number | null;
  // Learning Mode tiers (1 = worst, 5 = best). Null when an indicator
  // could not be rated (missing source data) or for non-graded fields.
  ratings?: QuoteRatings;
}

export interface QuoteRatings {
  pe10: number | null;
  pfcf10: number | null;
  peg: number | null;
  pfcfPeg: number | null;
  debtToEquity: number | null;
  debtExLeaseToEquity: number | null;
  liabilitiesToEquity: number | null;
  currentRatio: number | null;
  debtToAvgEarnings: number | null;
  debtToAvgFCF: number | null;
  overall: number | null;
  methodologyVersion: string;
}

interface QuoteError {
  error: string;
  code?: string;
  scope?: LookupScope;
  limit?: number;
  used?: number;
}

export type LookupScope = "anonymous" | "unverified" | "verified";

/** Thrown by fetchQuote when the daily company-lookup cap is hit (HTTP 429
 *  with code "lookup_limit"). Carries enough context for the UI to decide
 *  between the auth modal (anonymous) and the email-verification prompt
 *  (logged-in but unverified). */
export class LookupLimitError extends Error {
  readonly scope: LookupScope;
  readonly limit: number | null;

  constructor(scope: LookupScope, limit: number | null) {
    super("lookup_limit_reached");
    this.name = "LookupLimitError";
    this.scope = scope;
    this.limit = limit;
  }
}

export type LookupLimitAction =
  | { kind: "auth-modal"; limit: number | null }
  | { kind: "verify-prompt"; limit: number | null };

/** Maps a query error to the UI response for a hit lookup cap, or null
 *  when the error is unrelated. Anonymous users are pushed to sign up;
 *  logged-in-but-unverified users are nudged to verify their email
 *  (the auth modal would be wrong — they already have an account). */
export function resolveLookupLimitAction(
  error: unknown,
): LookupLimitAction | null {
  if (!(error instanceof LookupLimitError)) return null;
  if (error.scope === "unverified") {
    return { kind: "verify-prompt", limit: error.limit };
  }
  return { kind: "auth-modal", limit: error.limit };
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

/** Default values for nullable fields — prevents undefined from crashing renders */
const DEFAULTS: Partial<QuoteResult> = {
  maxYearsAvailable: 10,
  marketCap: null,
  pe10: null, avgAdjustedNetIncome: null, pe10Error: null,
  pe10CalculationDetails: [], pe10AnnualData: false,
  pfcf10: null, avgAdjustedFCF: null, pfcf10Error: null,
  pfcf10CalculationDetails: [], pfcf10AnnualData: false,
  debtToEquity: null, debtExLeaseToEquity: null, liabilitiesToEquity: null, currentRatio: null,
  leverageError: null, leverageDate: null,
  totalDebt: null, totalLease: null, totalLiabilities: null, stockholdersEquity: null,
  debtToAvgEarnings: null, debtToAvgFCF: null,
  peg: null, earningsCAGR: null, pegError: null,
  earningsCAGRMethod: null, earningsCAGRExcludedYears: [],
  pfcfPeg: null, fcfCAGR: null, pfcfPegError: null,
  fcfCAGRMethod: null, fcfCAGRExcludedYears: [],
  roe: null, priceToBook: null,
};

export async function fetchQuote(ticker: string): Promise<QuoteResult> {
  const response = await fetch(`/api/quote/${ticker}/`, {
    credentials: "include",
  });

  if (!response.ok) {
    const data = (await parseJSON(response)) as QuoteError | null;
    if (response.status === 429 && data?.code === "lookup_limit") {
      throw new LookupLimitError(
        data.scope ?? "anonymous",
        data.limit ?? null,
      );
    }
    const fallback =
      response.status === 404
        ? `Ticker "${ticker}" não encontrado. Verifique o código e tente novamente.`
        : "Não foi possível obter os dados no momento. Tente novamente mais tarde.";
    throw new Error(data?.error || fallback);
  }

  const raw = await response.json();
  return { ...DEFAULTS, ...raw } as QuoteResult;
}

export type { QuoteResult };
export type { QuoteRatings as QuoteRatingsType };

export function usePE10(ticker: string | null, initialData?: QuoteResult) {
  return useQuery({
    queryKey: ["pe10", ticker],
    queryFn: () => fetchQuote(ticker!),
    enabled: !!ticker,
    retry: false,
    staleTime: 15 * 60 * 1000,
    initialData,
  });
}
