"use client";

import Link from "next/link";
import { useCompareData } from "../hooks/useCompareData";
import { useTranslation, type TranslationKey } from "../i18n";
import { br } from "../utils/format";
import type { QuoteResult } from "../hooks/usePE10";
import "../styles/list-card.css";

/* ── Column definitions for compact list view ── */

interface ListCardColumnDef {
  key: string;
  label: string;
  format: (quoteResult: QuoteResult) => string | null;
  value: (quoteResult: QuoteResult) => number | null;
}

const MAX_VISIBLE_TICKERS = 5;

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

export function ListCard({ listId, name, tickers, years }: ListCardProps) {
  const { t } = useTranslation();
  const entries = useCompareData(tickers, years);
  const columns = getListCardColumns(years, t);
  const visibleEntries = entries.slice(0, MAX_VISIBLE_TICKERS);
  const hiddenCount = tickers.length - MAX_VISIBLE_TICKERS;
  const compareUrl = `/${tickers[0]}/comparar?listId=${listId}`;
  const isLoading = entries.length > 0 && entries.every((entry) => entry.isLoading);

  return (
    <div className={`list-card ${isLoading ? "list-card-loading" : ""}`}>
      <div className="list-card-header">
        <span className="list-card-name" title={name}>{name}</span>
        <Link href={compareUrl} className="list-card-link">
          {t("lists.view_full")}
        </Link>
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
        <tbody>
          {visibleEntries.map((entry) => {
            if (entry.isLoading || !entry.data) {
              return (
                <tr key={entry.ticker}>
                  <td className="list-card-ticker">{entry.ticker}</td>
                  {columns.map((column) => (
                    <td key={column.key} className="list-card-td">&mdash;</td>
                  ))}
                </tr>
              );
            }

            return (
              <tr key={entry.ticker}>
                <td className="list-card-ticker">{entry.ticker}</td>
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
    </div>
  );
}
