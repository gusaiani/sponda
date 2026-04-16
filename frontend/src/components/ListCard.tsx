"use client";

import Link from "next/link";
import { useLayoutEffect, useRef, useState } from "react";
import { useCompareData } from "../hooks/useCompareData";
import { useTranslation, type TranslationKey } from "../i18n";
import { br, logoUrl } from "../utils/format";
import type { QuoteResult } from "../hooks/usePE10";
import "../styles/list-card.css";

/* ── Column definitions for compact list view ── */

interface ListCardColumnDef {
  key: string;
  label: string;
  format: (quoteResult: QuoteResult) => string | null;
  value: (quoteResult: QuoteResult) => number | null;
}

const MIN_VISIBLE_TICKERS = 5;
const MAX_VISIBLE_TICKERS = 9;
const ESTIMATED_ROW_HEIGHT_PX = 22;

interface ComputeVisibleRowCountInput {
  availableHeight: number;
  rowHeight: number;
  totalRows: number;
  minRows: number;
  maxRows?: number;
}

export function computeVisibleRowCount({
  availableHeight,
  rowHeight,
  totalRows,
  minRows,
  maxRows,
}: ComputeVisibleRowCountInput): number {
  const cap = maxRows !== undefined ? Math.min(totalRows, maxRows) : totalRows;
  if (rowHeight <= 0) return Math.min(cap, minRows);
  const fits = Math.floor(availableHeight / rowHeight);
  const atLeastMin = Math.max(fits, minRows);
  return Math.min(cap, atLeastMin);
}

export function getListCardColumns(years: number, t: (key: TranslationKey) => string): ListCardColumnDef[] {
  const n = years;
  return [
    { key: "pe10", label: `${t("compare.col_pe")}${n}`, format: (quoteResult) => quoteResult.pe10 !== null ? br(quoteResult.pe10, 1) : null, value: (quoteResult) => quoteResult.pe10 },
    { key: "pfcf10", label: `${t("compare.col_pfcf")}${n}`, format: (quoteResult) => quoteResult.pfcf10 !== null ? br(quoteResult.pfcf10, 1) : null, value: (quoteResult) => quoteResult.pfcf10 },
    { key: "peg", label: `${t("compare.col_peg")}${n}`, format: (quoteResult) => quoteResult.peg !== null ? br(quoteResult.peg, 2) : null, value: (quoteResult) => quoteResult.peg },
    { key: "earningsCAGR", label: `${t("compare.col_cagr_earnings")}${n}`, format: (quoteResult) => quoteResult.earningsCAGR !== null ? `${br(quoteResult.earningsCAGR, 1)}%` : null, value: (quoteResult) => quoteResult.earningsCAGR },
    { key: "debtToEquity", label: t("compare.col_debt_to_equity"), format: (quoteResult) => quoteResult.debtToEquity !== null ? br(quoteResult.debtToEquity, 2) : null, value: (quoteResult) => quoteResult.debtToEquity },
    { key: "roe", label: `${t("compare.col_roe")}${n}`, format: (quoteResult) => quoteResult.roe !== null ? `${br(quoteResult.roe, 1)}%` : null, value: (quoteResult) => quoteResult.roe },
  ];
}

/* ── Component ── */

interface ListCardProps {
  listId: number;
  name: string;
  tickers: string[];
  years: number;
}

function TickerCell({ ticker }: { ticker: string }) {
  return (
    <td className="list-card-ticker">
      <span className="list-card-ticker-inner">
        <img
          className="list-card-logo"
          src={logoUrl(ticker)}
          alt=""
          onError={(event) => {
            (event.target as HTMLImageElement).style.visibility = "hidden";
          }}
        />
        {ticker}
      </span>
    </td>
  );
}

export function ListCard({ listId, name, tickers, years }: ListCardProps) {
  const { t, locale } = useTranslation();
  const entries = useCompareData(tickers, years);
  const columns = getListCardColumns(years, t);
  const compareUrl = `/${locale}/${tickers[0]}/comparar?listId=${listId}`;
  const isLoading = entries.length > 0 && entries.every((entry) => entry.isLoading);

  const cardRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLTableSectionElement>(null);
  const [visibleCount, setVisibleCount] = useState(Math.min(tickers.length, MAX_VISIBLE_TICKERS, MIN_VISIBLE_TICKERS));

  useLayoutEffect(() => {
    const cardElement = cardRef.current;
    const bodyElement = bodyRef.current;
    if (!cardElement || !bodyElement) return;

    const measure = () => {
      const cardRect = cardElement.getBoundingClientRect();
      const bodyRect = bodyElement.getBoundingClientRect();
      const footerElement = cardElement.querySelector<HTMLElement>(".list-card-footer");
      const footerHeight = footerElement ? footerElement.getBoundingClientRect().height : 0;
      const cardBottomPadding = parseFloat(getComputedStyle(cardElement).paddingBottom) || 0;
      const firstRow = bodyElement.querySelector<HTMLTableRowElement>("tr");
      const measuredRowHeight = firstRow ? firstRow.getBoundingClientRect().height : 0;
      const rowHeight = measuredRowHeight > 0 ? measuredRowHeight : ESTIMATED_ROW_HEIGHT_PX;
      const availableHeight = cardRect.bottom - cardBottomPadding - footerHeight - bodyRect.top;
      setVisibleCount(
        computeVisibleRowCount({
          availableHeight,
          rowHeight,
          totalRows: tickers.length,
          minRows: MIN_VISIBLE_TICKERS,
          maxRows: MAX_VISIBLE_TICKERS,
        }),
      );
    };

    measure();
    const resizeObserver = new ResizeObserver(measure);
    resizeObserver.observe(cardElement);
    return () => resizeObserver.disconnect();
  }, [tickers.length]);

  const effectiveVisibleCount = Math.min(visibleCount, tickers.length);
  const visibleEntries = entries.slice(0, effectiveVisibleCount);
  const hiddenCount = tickers.length - effectiveVisibleCount;

  return (
    <div ref={cardRef} className={`list-card ${isLoading ? "list-card-loading" : ""}`}>
      <div className="list-card-header">
        <span className="list-card-name" title={name}>{name}</span>
      </div>

      <table className="list-card-table">
        <thead>
          <tr>
            <th className="list-card-th" />
            {columns.map((column) => (
              <th key={column.key} className="list-card-th">{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody ref={bodyRef}>
          {visibleEntries.map((entry) => {
            if (entry.isLoading || !entry.data) {
              return (
                <tr key={entry.ticker}>
                  <TickerCell ticker={entry.ticker} />
                  {columns.map((column) => (
                    <td key={column.key} className="list-card-td">&mdash;</td>
                  ))}
                </tr>
              );
            }

            return (
              <tr key={entry.ticker}>
                <TickerCell ticker={entry.ticker} />
                {columns.map((column) => {
                  const formatted = column.format(entry.data!);
                  return (
                    <td key={column.key} className="list-card-td">
                      {formatted !== null ? formatted : <span className="list-card-null">&mdash;</span>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>

      {hiddenCount > 0 && (
        <p className="list-card-more">{t("lists.more", { count: hiddenCount })}</p>
      )}

      <div className="list-card-footer">
        <Link href={compareUrl} className="list-card-link">
          {t("lists.view_full")}
        </Link>
      </div>
    </div>
  );
}
