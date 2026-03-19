/**
 * Derives all year-dependent metrics client-side by slicing the full
 * calculation-details arrays to the requested number of years.
 *
 * This avoids re-fetching from the server when the user moves the slider.
 */
import type { QuoteResult } from "./usePE10";

/* ── CAGR (port of backend/quotes/cagr.py) ── */

interface CAGRResult {
  cagr: number | null;
  method: "endpoint" | "regression" | null;
  error: string | null;
  excludedYears: number[];
}

function computeCAGR(yearlyValues: [number, number][]): CAGRResult {
  if (yearlyValues.length < 2) {
    return { cagr: null, method: null, error: "Dados insuficientes", excludedYears: [] };
  }

  const sorted = [...yearlyValues].sort((a, b) => a[0] - b[0]);
  const [oldestYear, oldestVal] = sorted[0];
  const [newestYear, newestVal] = sorted[sorted.length - 1];
  const nYears = newestYear - oldestYear;

  if (nYears < 1) {
    return { cagr: null, method: null, error: "Dados insuficientes", excludedYears: [] };
  }

  // Try endpoint CAGR
  if (oldestVal > 0 && newestVal > 0) {
    const cagr = (Math.pow(newestVal / oldestVal, 1 / nYears) - 1) * 100;
    return { cagr: Math.round(cagr * 100) / 100, method: "endpoint", error: null, excludedYears: [] };
  }

  // Fallback: log-linear regression on positive years
  const positive = sorted.filter(([, v]) => v > 0);
  const excluded = sorted.filter(([, v]) => v <= 0).map(([y]) => y);

  if (positive.length < 2) {
    return { cagr: null, method: null, error: "Dados insuficientes — anos negativos/zero", excludedYears: excluded };
  }

  const xs = positive.map(([y]) => y);
  const ys = positive.map(([, v]) => Math.log(v));
  const n = xs.length;
  const xMean = xs.reduce((s, x) => s + x, 0) / n;
  const yMean = ys.reduce((s, y) => s + y, 0) / n;

  const numerator = xs.reduce((s, x, i) => s + (x - xMean) * (ys[i] - yMean), 0);
  const denominator = xs.reduce((s, x) => s + (x - xMean) ** 2, 0);

  if (denominator === 0) {
    return { cagr: null, method: null, error: "Dados insuficientes", excludedYears: excluded };
  }

  const slope = numerator / denominator;
  const cagr = (Math.exp(slope) - 1) * 100;
  return { cagr: Math.round(cagr * 100) / 100, method: "regression", error: null, excludedYears: excluded };
}

/* ── Main derivation ── */

export function deriveForYears(full: QuoteResult, years: number): QuoteResult {
  const maxEarnings = full.pe10CalculationDetails.length;
  const maxFCF = full.pfcf10CalculationDetails.length;

  // Slice to requested years (details are sorted most-recent-first)
  const earningsSlice = full.pe10CalculationDetails.slice(0, Math.min(years, maxEarnings));
  const fcfSlice = full.pfcf10CalculationDetails.slice(0, Math.min(years, maxFCF));

  const earningsYears = earningsSlice.length;
  const fcfYears = fcfSlice.length;

  // PE
  let pe10: number | null = null;
  let avgAdjustedNetIncome: number | null = null;
  let pe10Error: string | null = null;

  if (earningsYears > 0) {
    const total = earningsSlice.reduce((s, y) => s + y.adjustedNetIncome, 0);
    avgAdjustedNetIncome = total / earningsYears;
    if (avgAdjustedNetIncome > 0 && full.marketCap) {
      pe10 = Math.round((full.marketCap / avgAdjustedNetIncome) * 100) / 100;
    } else if (avgAdjustedNetIncome <= 0) {
      pe10Error = "lucro médio negativo";
    }
  } else {
    pe10Error = "Sem dados de lucro disponíveis";
  }

  // PFCF
  let pfcf10: number | null = null;
  let avgAdjustedFCF: number | null = null;
  let pfcf10Error: string | null = null;

  if (fcfYears > 0) {
    const total = fcfSlice.reduce((s, y) => s + y.adjustedFCF, 0);
    avgAdjustedFCF = total / fcfYears;
    if (avgAdjustedFCF > 0 && full.marketCap) {
      pfcf10 = Math.round((full.marketCap / avgAdjustedFCF) * 100) / 100;
    } else if (avgAdjustedFCF <= 0) {
      pfcf10Error = "FCL médio negativo";
    }
  } else {
    pfcf10Error = "Sem dados de fluxo de caixa disponíveis";
  }

  // Debt coverage
  let debtToAvgEarnings: number | null = null;
  if (full.totalDebt != null && avgAdjustedNetIncome && avgAdjustedNetIncome > 0) {
    debtToAvgEarnings = Math.round((full.totalDebt / avgAdjustedNetIncome) * 100) / 100;
  }
  let debtToAvgFCF: number | null = null;
  if (full.totalDebt != null && avgAdjustedFCF && avgAdjustedFCF > 0) {
    debtToAvgFCF = Math.round((full.totalDebt / avgAdjustedFCF) * 100) / 100;
  }

  // CAGR (earnings)
  const earningsCAGRInput: [number, number][] = earningsSlice.map((y) => [y.year, y.adjustedNetIncome]);
  const earningsCagr = computeCAGR(earningsCAGRInput);

  // PEG
  let peg: number | null = null;
  let pegError: string | null = null;
  if (pe10 === null) {
    pegError = `P/L${earningsYears} indisponível`;
  } else if (earningsCagr.cagr === null) {
    pegError = earningsCagr.error;
  } else if (earningsCagr.cagr <= 0) {
    pegError = "crescimento negativo";
  } else {
    peg = Math.round((pe10 / earningsCagr.cagr) * 100) / 100;
  }

  // CAGR (FCF)
  const fcfCAGRInput: [number, number][] = fcfSlice.map((y) => [y.year, y.adjustedFCF]);
  const fcfCagr = computeCAGR(fcfCAGRInput);

  // PFCLG
  let pfcfPeg: number | null = null;
  let pfcfPegError: string | null = null;
  if (pfcf10 === null) {
    pfcfPegError = `P/FCL${fcfYears} indisponível`;
  } else if (fcfCagr.cagr === null) {
    pfcfPegError = fcfCagr.error;
  } else if (fcfCagr.cagr <= 0) {
    pfcfPegError = "crescimento negativo";
  } else {
    pfcfPeg = Math.round((pfcf10 / fcfCagr.cagr) * 100) / 100;
  }

  return {
    ...full,
    // PE
    pe10,
    avgAdjustedNetIncome,
    pe10YearsOfData: earningsYears,
    pe10Label: `PE${earningsYears}`,
    pe10Error,
    pe10CalculationDetails: earningsSlice,
    // PFCF
    pfcf10,
    avgAdjustedFCF,
    pfcf10YearsOfData: fcfYears,
    pfcf10Label: `PFCF${fcfYears}`,
    pfcf10Error,
    pfcf10CalculationDetails: fcfSlice,
    // Debt coverage
    debtToAvgEarnings,
    debtToAvgFCF,
    // PEG
    peg,
    earningsCAGR: earningsCagr.cagr,
    pegError,
    earningsCAGRMethod: earningsCagr.method,
    earningsCAGRExcludedYears: earningsCagr.excludedYears,
    // PFCLG
    pfcfPeg,
    fcfCAGR: fcfCagr.cagr,
    pfcfPegError,
    fcfCAGRMethod: fcfCagr.method,
    fcfCAGRExcludedYears: fcfCagr.excludedYears,
  };
}
