import { fetchFromDjango } from "../../../lib/django-fetch";
import { requestIdentityHeaders } from "../../../lib/requestIdentity";
import type { QuoteResult } from "../../../hooks/usePE10";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

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

export type FetchQuoteServerResult =
  | { data: QuoteResult; error: null }
  | { data: null; error: "not-found" | "server-error" };

export async function fetchQuoteServer(ticker: string): Promise<FetchQuoteServerResult> {
  // Outside the try: `headers()` is also the dynamic-render signal, and the
  // quote must never be prerendered under someone else's session.
  const identityHeaders = await requestIdentityHeaders();

  try {
    // fetchFromDjango rather than fetch: gunicorn's sync workers close the
    // connection on every response and Node's client intermittently fails to
    // parse that, so a transport failure gets one retry on a fresh socket.
    const response = await fetchFromDjango(`${DJANGO_API_URL}/api/quote/${ticker}/`, {
      cache: "no-store",
      headers: identityHeaders,
    });

    if (!response) {
      return { data: null, error: "server-error" };
    }

    if (response.status === 404) {
      return { data: null, error: "not-found" };
    }

    if (!response.ok) {
      return { data: null, error: "server-error" };
    }

    const raw = await response.json();
    return { data: { ...DEFAULTS, ...raw } as QuoteResult, error: null };
  } catch {
    return { data: null, error: "server-error" };
  }
}
