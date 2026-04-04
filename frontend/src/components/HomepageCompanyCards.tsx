"use client";

import Link from "next/link";
import { useCompareData } from "../hooks/useCompareData";
import { useFavorites } from "../hooks/useFavorites";
import { useAuth } from "../hooks/useAuth";
import { useTranslation } from "../i18n";
import { br, formatLargeNumber } from "../utils/format";
import type { QuoteResult } from "../hooks/usePE10";
import "../styles/homepage-cards.css";

const HOMEPAGE_MAX_CARDS = 8;

const DEFAULT_TICKERS = [
  "PETR4", "VALE3", "ITUB4", "WEGE3",
  "ABEV3", "BBAS3", "RENT3", "SUZB3",
];

interface SelectOptions {
  isAuthenticated: boolean;
  favoriteTickers: string[];
  defaultTickers: string[];
  maxCards: number;
}

export function selectHomepageTickers({
  isAuthenticated,
  favoriteTickers,
  defaultTickers,
  maxCards,
}: SelectOptions): string[] {
  if (isAuthenticated && favoriteTickers.length > 0) {
    return favoriteTickers.slice(0, maxCards);
  }
  return defaultTickers.slice(0, maxCards);
}

export function formatMarketCap(value: number | null): string | null {
  if (value === null) return null;
  const abs = Math.abs(value);
  if (abs >= 1e12) return `R$ ${br(value / 1e9, 0)}B`;
  if (abs >= 1e9) return `R$ ${br(value / 1e9, 1)}B`;
  if (abs >= 1e6) return `R$ ${br(value / 1e6, 0)}M`;
  return `R$ ${br(value, 0)}`;
}

interface IndicatorProps {
  label: string;
  value: string | null;
  suffix?: string;
}

function Indicator({ label, value, suffix = "" }: IndicatorProps) {
  return (
    <div className="hcc-indicator">
      <span className="hcc-indicator-label">{label}</span>
      <span className="hcc-indicator-value">
        {value !== null ? `${value}${suffix}` : "·"}
      </span>
    </div>
  );
}

export function CompanyCard({ data, isLoading, logoOverride }: { data: QuoteResult | null; isLoading: boolean; logoOverride?: string }) {
  const { t } = useTranslation();

  if (isLoading || !data) {
    return (
      <div className="hcc-card hcc-card-loading">
        <div className="hcc-card-header">
          <div className="hcc-logo-placeholder" />
          <div className="hcc-name-placeholder" />
        </div>
        <div className="hcc-indicators-grid">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="hcc-indicator-placeholder" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <Link href={`/${data.ticker}`} className="hcc-card">
      <div className="hcc-card-header">
        {(logoOverride || data.logo) && (
          <img
            className="hcc-logo"
            src={logoOverride || data.logo}
            alt=""
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
        )}
        <div className="hcc-name-block">
          <span className="hcc-name">{data.name}</span>
          <span className="hcc-ticker">{data.ticker}</span>
        </div>
      </div>

      <div className="hcc-price-row">
        <div className="hcc-price-item">
          <span className="hcc-price-label">{t("homepage.price")}</span>
          <span className="hcc-price">R$ {br(data.currentPrice, 2)}</span>
        </div>
        {data.marketCap && (
          <div className="hcc-price-item">
            <span className="hcc-price-label">{t("homepage.market_cap")}</span>
            <span className="hcc-market-cap">{formatMarketCap(data.marketCap)}</span>
          </div>
        )}
      </div>

      <div className="hcc-indicators-grid">
        {/* Balance sheet */}
        <Indicator label={t("homepage.equity")} value={data.stockholdersEquity !== null ? formatLargeNumber(data.stockholdersEquity) : null} />
        <Indicator label={t("homepage.liabilities")} value={data.totalLiabilities !== null ? formatLargeNumber(data.totalLiabilities) : null} />
        <Indicator label={t("homepage.gross_debt")} value={data.totalDebt !== null ? formatLargeNumber(data.totalDebt - (data.totalLease ?? 0)) : null} />
        <Indicator label={t("homepage.current_ratio")} value={data.currentRatio !== null ? br(data.currentRatio, 2) : null} />
        <Indicator label={t("fundamentals.col.debt_equity")} value={data.debtToEquity !== null ? br(data.debtToEquity, 2) : null} />
        <Indicator label="Dív/FCL" value={data.debtToAvgFCF !== null ? br(data.debtToAvgFCF, 1) : null} />
        {/* Valuation & growth */}
        <Indicator label="P/L10" value={data.pe10 !== null ? br(data.pe10, 1) : null} />
        <Indicator label="P/FCL10" value={data.pfcf10 !== null ? br(data.pfcf10, 1) : null} />
        <Indicator label="PEG" value={data.peg !== null ? br(data.peg, 2) : null} />
        <Indicator label="PFCLG" value={data.pfcfPeg !== null ? br(data.pfcfPeg, 2) : null} />
        <Indicator label="CAGR L" value={data.earningsCAGR !== null ? br(data.earningsCAGR, 1) : null} suffix="%" />
        <Indicator label="CAGR FCL" value={data.fcfCAGR !== null ? br(data.fcfCAGR, 1) : null} suffix="%" />
        <Indicator label="ROE" value={data.roe !== null ? br(data.roe, 1) : null} suffix="%" />
        <Indicator label="P/VPA" value={data.priceToBook !== null ? br(data.priceToBook, 2) : null} />
      </div>
    </Link>
  );
}

export function HomepageCompanyCards() {
  const { isAuthenticated } = useAuth();
  const { favoriteTickers } = useFavorites();

  const tickers = selectHomepageTickers({
    isAuthenticated,
    favoriteTickers,
    defaultTickers: DEFAULT_TICKERS,
    maxCards: HOMEPAGE_MAX_CARDS,
  });

  const entries = useCompareData(tickers, 10);

  return (
    <section className="hcc-section">
      <div className="hcc-grid">
        {entries.map((entry) => (
          <CompanyCard
            key={entry.ticker}
            data={entry.data}
            isLoading={entry.isLoading}
          />
        ))}
      </div>
    </section>
  );
}
