import { headers } from "next/headers";

import { fetchFromDjango } from "../../../lib/django-fetch";
import type { QuoteResult } from "../../../hooks/usePE10";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8710";

/**
 * Headers that tell Django who is actually asking.
 *
 * `quotes.client_ip.client_ip()` reads them in this order and falls through
 * to REMOTE_ADDR last. Cloudflare overwrites `CF-Connecting-IP` with the true
 * client address on every request, so it cannot be spoofed from outside;
 * `X-Forwarded-For` is what nginx sets (`$proxy_add_x_forwarded_for`) and is
 * the next best signal when Cloudflare is not in front.
 */
const CLIENT_IP_HEADERS = ["cf-connecting-ip", "x-forwarded-for", "x-real-ip"] as const;

/**
 * Copy the caller's IP headers onto the server-to-server request.
 *
 * Without this the fetch reaches Django from 127.0.0.1 with nothing else to
 * go on, so `client_ip()` hashes the loopback address and EVERY
 * server-rendered company page in production shares one anonymous bucket of
 * `SPONDA_ANON_LOOKUPS_PER_DAY` distinct tickers per day. Past the cap the
 * SSR fetch gets a 429, `page.tsx` reads any non-404 as `server-error`, and
 * the page quietly falls back to client-side fetching. Nobody sees an error;
 * the prefetch just stops working for the rest of the day.
 *
 * Only the IP headers are copied. The cookie is deliberately left behind so
 * the request stays anonymous, which is what `serverApi.serverFetch` is for
 * when a page does need the user's session.
 */
async function clientIpHeaders(): Promise<Record<string, string>> {
  let incoming: Headers;
  try {
    incoming = await headers();
  } catch {
    // Called outside a request scope. Nothing to forward, and not worth
    // failing the page over.
    return {};
  }

  const forwarded: Record<string, string> = {};
  for (const name of CLIENT_IP_HEADERS) {
    const value = incoming.get(name);
    if (value) forwarded[name] = value;
  }
  return forwarded;
}

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
  try {
    const response = await fetchFromDjango(`${DJANGO_API_URL}/api/quote/${ticker}/`, {
      cache: "no-store",
      headers: await clientIpHeaders(),
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
