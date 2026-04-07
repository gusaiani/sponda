"use client";

import Link from "next/link";
import { useCompareData } from "../hooks/useCompareData";
import { useFavorites } from "../hooks/useFavorites";
import { useAuth } from "../hooks/useAuth";
import { useRegion } from "../hooks/useRegion";
import { useTranslation } from "../i18n";
import { br, formatLargeNumber, currencySymbol, logoUrl } from "../utils/format";
import { getDefaultTickers } from "../utils/suggestedCompanies";
import type { QuoteResult } from "../hooks/usePE10";
import "../styles/homepage-cards.css";

const HOMEPAGE_MAX_CARDS = 8;

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

export function formatMarketCap(value: number | null, ticker: string = ""): string | null {
  if (value === null) return null;
  const currency = ticker ? currencySymbol(ticker) : "R$";
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${currency} ${br(value / 1e9, 0)}B`;
  if (abs >= 1e9) return `${currency} ${br(value / 1e9, 1)}B`;
  if (abs >= 1e6) return `${currency} ${br(value / 1e6, 0)}M`;
  return `${currency} ${br(value, 0)}`;
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

export function CompanyCard({ data, isLoading }: { data: QuoteResult | null; isLoading: boolean }) {
  const { t, locale } = useTranslation();

  if (isLoading || !data) {
    return (
      <div className="hcc-card hcc-card-loading">
        <div className="hcc-card-header">
          <div className="hcc-logo-placeholder" />
          <div className="hcc-name-block">
            <div className="hcc-name-placeholder" />
            <div className="hcc-ticker-placeholder" />
          </div>
        </div>
        <div className="hcc-price-row">
          <div className="hcc-price-item">
            <span className="hcc-price-label">&nbsp;</span>
            <span className="hcc-price">&nbsp;</span>
          </div>
          <div className="hcc-price-item">
            <span className="hcc-price-label">&nbsp;</span>
            <span className="hcc-market-cap">&nbsp;</span>
          </div>
        </div>
        <div className="hcc-indicators-grid">
          {Array.from({ length: 14 }).map((_, i) => (
            <div key={i} className="hcc-indicator">
              <span className="hcc-indicator-label">&nbsp;</span>
              <span className="hcc-indicator-value">&nbsp;</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <Link href={`/${locale}/${data.ticker}`} className="hcc-card">
      <div className="hcc-card-header">
        <img
          className="hcc-logo"
          src={logoUrl(data.ticker)}
          alt=""
          loading="lazy"
          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
        <div className="hcc-name-block">
          <span className="hcc-name">{data.name}</span>
          <span className="hcc-ticker">{data.ticker}</span>
        </div>
      </div>

      <div className="hcc-price-row">
        <div className="hcc-price-item">
          <span className="hcc-price-label">{t("homepage.price")}</span>
          <span className="hcc-price">{currencySymbol(data.ticker)} {br(data.currentPrice, 2)}</span>
        </div>
        {data.marketCap && (
          <div className="hcc-price-item">
            <span className="hcc-price-label">{t("homepage.market_cap")}</span>
            <span className="hcc-market-cap">{formatMarketCap(data.marketCap, data.ticker)}</span>
          </div>
        )}
      </div>

      <div className="hcc-indicators-grid">
        {/* Balance sheet */}
        <Indicator label={t("homepage.equity")} value={data.stockholdersEquity !== null ? formatLargeNumber(data.stockholdersEquity, data.ticker) : null} />
        <Indicator label={t("homepage.liabilities")} value={data.totalLiabilities !== null ? formatLargeNumber(data.totalLiabilities, data.ticker) : null} />
        <Indicator label={t("homepage.gross_debt")} value={data.totalDebt !== null ? formatLargeNumber(data.totalDebt - (data.totalLease ?? 0), data.ticker) : null} />
        <Indicator label={t("homepage.current_ratio")} value={data.currentRatio !== null ? br(data.currentRatio, 2) : null} />
        <Indicator label={t("fundamentals.col.debt_equity")} value={data.debtToEquity !== null ? br(data.debtToEquity, 2) : null} />
        <Indicator label={t("homepage.debt_fcf")} value={data.debtToAvgFCF !== null ? br(data.debtToAvgFCF, 1) : null} />
        {/* Valuation & growth */}
        <Indicator label={t("homepage.pe10")} value={data.pe10 !== null ? br(data.pe10, 1) : null} />
        <Indicator label={t("homepage.pfcf10")} value={data.pfcf10 !== null ? br(data.pfcf10, 1) : null} />
        <Indicator label="PEG" value={data.peg !== null ? br(data.peg, 2) : null} />
        <Indicator label="PFCLG" value={data.pfcfPeg !== null ? br(data.pfcfPeg, 2) : null} />
        <Indicator label={t("homepage.cagr_earnings_short")} value={data.earningsCAGR !== null ? br(data.earningsCAGR, 1) : null} suffix="%" />
        <Indicator label={t("homepage.cagr_fcf_short")} value={data.fcfCAGR !== null ? br(data.fcfCAGR, 1) : null} suffix="%" />
        <Indicator label="ROE" value={data.roe !== null ? br(data.roe, 1) : null} suffix="%" />
        <Indicator label={t("homepage.price_to_book")} value={data.priceToBook !== null ? br(data.priceToBook, 2) : null} />
      </div>
    </Link>
  );
}

export function HomepageCompanyCards() {
  const { isAuthenticated } = useAuth();
  const { favoriteTickers } = useFavorites();
  const region = useRegion();

  const tickers = selectHomepageTickers({
    isAuthenticated,
    favoriteTickers,
    defaultTickers: getDefaultTickers(region),
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
