import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useCompareData, type CompareEntry } from "../hooks/useCompareData";
import { useSavedLists } from "../hooks/useSavedLists";
import { useAuth } from "../hooks/useAuth";
import { useFavorites } from "../hooks/useFavorites";
import { useDragGhost } from "../hooks/useDragGhost";
import { useTranslation, type TranslationKey } from "../i18n";
import { AuthModal } from "./AuthModal";
import { CompanySearchInput } from "./CompanySearchInput";
import { br, logoUrl } from "../utils/format";
import { buildOwnerSwapUrl } from "../utils/tabs";
import type { QuoteResult } from "../hooks/usePE10";
import type { FundamentalsYear } from "../hooks/useFundamentals";
import "../styles/compare.css";

/* ── Column definitions ── */

export interface CompareRowData {
  quote: QuoteResult;
  recent: FundamentalsYear | null;
  pe: number | null;
  pfcf: number | null;
}

interface ColumnDef {
  key: string;
  label: string;
  group: "balanco" | "resultado" | "caixa" | "retorno";
  format: (d: CompareRowData) => string | null;
  value: (d: CompareRowData) => number | null;
}

type SortDir = "asc" | "desc";
interface SortState {
  key: string;
  dir: SortDir;
}

function millions(value: number | null): string | null {
  if (value === null) return null;
  return br(value / 1e6, 0);
}

function ratio(value: number | null): string | null {
  if (value === null) return null;
  return br(value, 2);
}

function ratio1(value: number | null): string | null {
  if (value === null) return null;
  return br(value, 1);
}

export function getColumns(years: number, t: (key: TranslationKey) => string): ColumnDef[] {
  return [
    // Balanço
    { key: "debtExLease", label: t("fundamentals.col.debt"), group: "balanco",
      format: (d) => millions(d.recent?.debtExLease ?? null),
      value: (d) => d.recent?.debtExLease ?? null,
    },
    { key: "totalLiabilities", label: t("fundamentals.col.liabilities"), group: "balanco",
      format: (d) => millions(d.recent?.totalLiabilities ?? null),
      value: (d) => d.recent?.totalLiabilities ?? null,
    },
    { key: "equity", label: t("fundamentals.col.equity"), group: "balanco",
      format: (d) => millions(d.recent?.stockholdersEquity ?? null),
      value: (d) => d.recent?.stockholdersEquity ?? null,
    },
    { key: "debtToEquity", label: t("fundamentals.col.debt_equity"), group: "balanco",
      format: (d) => ratio(d.recent?.debtToEquity ?? null),
      value: (d) => d.recent?.debtToEquity ?? null,
    },
    { key: "liabToEquity", label: t("fundamentals.col.liab_equity"), group: "balanco",
      format: (d) => ratio(d.recent?.liabilitiesToEquity ?? null),
      value: (d) => d.recent?.liabilitiesToEquity ?? null,
    },
    { key: "currentRatio", label: t("fundamentals.col.current_ratio"), group: "balanco",
      format: (d) => ratio(d.recent?.currentRatio ?? null),
      value: (d) => d.recent?.currentRatio ?? null,
    },
    // Resultado
    { key: "revenue", label: t("fundamentals.col.revenue"), group: "resultado",
      format: (d) => millions(d.recent?.revenue ?? null),
      value: (d) => d.recent?.revenue ?? null,
    },
    { key: "netIncome", label: t("fundamentals.col.net_income"), group: "resultado",
      format: (d) => millions(d.recent?.netIncome ?? null),
      value: (d) => d.recent?.netIncome ?? null,
    },
    { key: "pe", label: `${t("fundamentals.col.pe")}${years}`, group: "resultado",
      format: (d) => ratio1(d.pe),
      value: (d) => d.pe,
    },
    // Caixa
    { key: "fcf", label: t("fundamentals.col.fcf"), group: "caixa",
      format: (d) => millions(d.recent?.fcf ?? null),
      value: (d) => d.recent?.fcf ?? null,
    },
    { key: "pfcf", label: `${t("fundamentals.col.pfcf")}${years}`, group: "caixa",
      format: (d) => ratio1(d.pfcf),
      value: (d) => d.pfcf,
    },
    { key: "operatingCF", label: t("fundamentals.col.operating_cf"), group: "caixa",
      format: (d) => millions(d.recent?.operatingCashFlow ?? null),
      value: (d) => d.recent?.operatingCashFlow ?? null,
    },
    // Retorno
    { key: "marketCap", label: t("fundamentals.col.market_cap"), group: "retorno",
      format: (d) => millions(d.quote.marketCap),
      value: (d) => d.quote.marketCap,
    },
    { key: "dividends", label: t("fundamentals.col.dividends"), group: "retorno",
      format: (d) => millions(d.recent?.dividendsPaid ?? null),
      value: (d) => d.recent?.dividendsPaid ?? null,
    },
  ];
}

const BALANCE_COUNT = 6;
const RESULTADO_COUNT = 3;
const CAIXA_COUNT = 3;
const RETORNO_COUNT = 2;

const GROUP_START_INDICES = new Set([
  BALANCE_COUNT,
  BALANCE_COUNT + RESULTADO_COUNT,
  BALANCE_COUNT + RESULTADO_COUNT + CAIXA_COUNT,
]);

/* ── Drag handle icon ── */

function DragIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      <circle cx="4" cy="2" r="1" />
      <circle cx="8" cy="2" r="1" />
      <circle cx="4" cy="6" r="1" />
      <circle cx="8" cy="6" r="1" />
      <circle cx="4" cy="10" r="1" />
      <circle cx="8" cy="10" r="1" />
    </svg>
  );
}

/* ── Component ── */

interface Props {
  currentTicker: string;
  years: number;
  maxYears: number;
  onYearsChange: (y: number) => void;
  extraTickers: string[];
  onExtraTickersChange: (tickers: string[]) => void;
  savedListId?: number | null;
}

export function CompareTab({ currentTicker, years, maxYears, onYearsChange, extraTickers, onExtraTickersChange, savedListId }: Props) {
  const { t, pluralize, locale } = useTranslation();
  const router = useRouter();
  const allTickers = [currentTicker, ...extraTickers];
  const entries = useCompareData(allTickers, years);
  const columns = getColumns(years, t);
  const dragIndexRef = useRef<number | null>(null);
  const { startGhost, stopGhost } = useDragGhost();
  const [sort, setSort] = useState<SortState | null>(null);
  const [saveName, setSaveName] = useState("");
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showRenameForm, setShowRenameForm] = useState(false);
  const [renameName, setRenameName] = useState("");
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authModalMessage, setAuthModalMessage] = useState<string | undefined>(undefined);
  const { isAuthenticated } = useAuth();
  const { favorites } = useFavorites();
  const { saveList, updateList, deleteList, lists } = useSavedLists();
  const queryClient = useQueryClient();
  // Find existing list: by explicit ID (from URL param) or by matching tickers
  const existingList = (() => {
    if (savedListId) {
      return lists.find((list) => list.id === savedListId);
    }
    // Fallback: match by exact ticker composition (order-independent)
    const tickerSet = new Set(allTickers);
    return lists.find((list) => {
      if (list.tickers.length !== tickerSet.size) return false;
      return list.tickers.every((ticker) => tickerSet.has(ticker));
    });
  })();
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-save when tickers or years change on an existing saved list
  useEffect(() => {
    if (!existingList) return;

    const tickersChanged = existingList.tickers.join(",") !== allTickers.join(",");
    const yearsChanged = existingList.years !== years;

    if (!tickersChanged && !yearsChanged) return;

    // Debounce auto-save by 1 second
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(() => {
      updateList.mutate({ id: existingList.id, tickers: allTickers, years });
    }, 1000);

    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [allTickers.join(","), years, existingList?.id]);

  function handleSort(key: string) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: "asc" };
      if (prev.dir === "asc") return { key, dir: "desc" };
      return null; // third click clears sort
    });
  }

  const sortedEntries = useMemo(() => {
    if (!sort) return entries;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return entries;

    return [...entries].sort((a, b) => {
      const va = a.data ? col.value({ quote: a.data, recent: a.recent, pe: a.pe, pfcf: a.pfcf }) : null;
      const vb = b.data ? col.value({ quote: b.data, recent: b.recent, pe: b.pe, pfcf: b.pfcf }) : null;
      // nulls always go to the bottom
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      return sort.dir === "asc" ? va - vb : vb - va;
    });
  }, [entries, sort, columns]);

  function handleAdd(ticker: string) {
    const upper = ticker.toUpperCase();
    if (!allTickers.includes(upper)) {
      onExtraTickersChange([...extraTickers, upper]);
    }
  }

  function handleRemove(ticker: string) {
    onExtraTickersChange(extraTickers.filter((t) => t !== ticker));
  }

  function handleReorder(fromIndex: number, toIndex: number) {
    if (fromIndex === toIndex) return;
    const reordered = sortedEntries.map((e) => e.ticker);
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);

    const newTop = reordered[0];
    if (newTop !== currentTicker) {
      const newExtras = reordered.slice(1);
      const targetUrl = buildOwnerSwapUrl(
        locale,
        newTop,
        newExtras,
        new URLSearchParams(window.location.search),
      );
      router.push(targetUrl);
      return;
    }

    onExtraTickersChange(reordered.filter((t) => t !== currentTicker));
    setSort(null); // clear sort after manual reorder
  }

  function sortIndicator(key: string) {
    if (!sort || sort.key !== key) return <span className="compare-sort-arrow compare-sort-inactive">↕</span>;
    return <span className="compare-sort-arrow">{sort.dir === "asc" ? "↑" : "↓"}</span>;
  }

  return (
    <div className="compare-container">
      {/* Scrollable table */}
      <div className="compare-scroll-wrapper">
        <table className="compare-table">
          <thead>
            {/* Group header */}
            <tr className="compare-group-row">
              <th className="compare-drag-col" />
              <th className="compare-sticky-col" />
              <th colSpan={BALANCE_COUNT}>{t("fundamentals.balance")}</th>
              <th colSpan={RESULTADO_COUNT} className="compare-group-separator">{t("fundamentals.income")}</th>
              <th colSpan={CAIXA_COUNT} className="compare-group-separator">{t("fundamentals.cash_flow")}</th>
              <th colSpan={RETORNO_COUNT} className="compare-group-separator">{t("fundamentals.returns")}</th>
              <th />
            </tr>
            {/* Column headers */}
            <tr>
              <th className="compare-drag-col" />
              <th className="compare-sticky-col">{t("compare.company")}</th>
              {columns.map((col, index) => (
                <th
                  key={col.key}
                  className={`compare-sortable-th ${GROUP_START_INDICES.has(index) ? "compare-group-separator" : ""}`}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label} {sortIndicator(col.key)}
                </th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {sortedEntries.map((entry, i) => (
              <CompareRow
                key={entry.ticker}
                entry={entry}
                index={i}
                isCurrentTicker={entry.ticker === currentTicker}
                onRemove={handleRemove}
                columns={columns}
                dragIndexRef={dragIndexRef}
                onReorder={handleReorder}
                totalRows={sortedEntries.length}
                startGhost={startGhost}
                stopGhost={stopGhost}
                isAuthenticated={isAuthenticated}
                onRequireAuth={() => {
                  setAuthModalMessage(t("compare.auth_reorder"));
                  setShowAuthModal(true);
                }}
              />
            ))}
            {/* Add company row */}
            <tr className="compare-add-row">
              <td className="compare-drag-col" />
              <td className="compare-sticky-col">
                <CompanySearchInput
                  onAdd={handleAdd}
                  excludeTickers={allTickers}
                />
              </td>
              <td colSpan={columns.length + 1} />
            </tr>
          </tbody>
        </table>
      </div>


      {/* Floating action buttons — always visible */}
      {!showSaveForm && !showDeleteConfirm && !showRenameForm && (
        existingList ? (
          <div className="compare-floating-actions">
            <button
              className="compare-save-floating compare-save-floating-secondary"
              onClick={() => {
                setRenameName(existingList.name);
                setShowRenameForm(true);
              }}
            >
              {t("compare.rename")}
            </button>
            <button
              className="compare-save-floating"
              onClick={() => {
                setSaveName(existingList.name + (locale === "pt" ? " (cópia)" : " (copy)"));
                setShowSaveForm(true);
              }}
            >
              {t("compare.duplicate")}
            </button>
            <button
              className="compare-save-floating compare-save-floating-danger"
              onClick={() => setShowDeleteConfirm(true)}
            >
              {t("common.delete")}
            </button>
          </div>
        ) : (
          <div className="compare-floating-actions">
            <button
              className={`compare-save-floating ${!isAuthenticated || favorites.length < 3 ? "compare-save-floating-prominent" : ""}`}
              onClick={() => {
                if (!isAuthenticated) {
                  setShowAuthModal(true);
                  return;
                }
                setShowSaveForm(true);
              }}
            >
              {t("compare.save_list")}
            </button>
          </div>
        )
      )}

      {/* Rename modal */}
      {showRenameForm && existingList && (
        <div className="compare-save-overlay" onClick={() => setShowRenameForm(false)}>
          <div className="compare-save-modal" onClick={(event) => event.stopPropagation()}>
            <h3 className="compare-save-modal-title">{t("compare.rename_list")}</h3>
            <form onSubmit={(event) => {
              event.preventDefault();
              if (!renameName.trim()) return;
              updateList.mutate(
                { id: existingList.id, name: renameName.trim() },
                { onSuccess: () => setShowRenameForm(false) },
              );
            }}>
              <input
                type="text"
                className="auth-input"
                placeholder={t("compare.new_name")}
                value={renameName}
                onChange={(event) => setRenameName(event.target.value)}
                autoFocus
              />
              <div className="compare-save-modal-actions">
                <button type="submit" className="auth-button" disabled={!renameName.trim()}>
                  {t("compare.rename")}
                </button>
                <button type="button" className="auth-button-secondary" onClick={() => setShowRenameForm(false)}>
                  {t("common.cancel")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      {showDeleteConfirm && existingList && (
        <div className="compare-save-overlay" onClick={() => setShowDeleteConfirm(false)}>
          <div className="compare-save-modal" onClick={(event) => event.stopPropagation()}>
            <h3 className="compare-save-modal-title">{t("compare.delete_list")}</h3>
            <p className="compare-save-modal-detail">
              {t("compare.delete_confirm")} "{existingList.name}"?
            </p>
            <div className="compare-save-modal-actions">
              <button
                className="auth-button compare-delete-button"
                onClick={() => {
                  deleteList.mutate(existingList.id);
                  setShowDeleteConfirm(false);
                }}
              >
                {t("common.delete")}
              </button>
              <button
                className="auth-button-secondary"
                onClick={() => setShowDeleteConfirm(false)}
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Save / Duplicate modal */}
      {showSaveForm && (
        <div className="compare-save-overlay" onClick={() => setShowSaveForm(false)}>
          <div className="compare-save-modal" onClick={(event) => event.stopPropagation()}>
            <h3 className="compare-save-modal-title">
              {existingList ? t("compare.duplicate_list") : t("compare.save_list")}
            </h3>
            <p className="compare-save-modal-detail">
              {allTickers.length} {t("common.companies")} · {years} {pluralize(years, "common.year_singular", "common.year_plural")}
            </p>
            <form onSubmit={(event) => {
                event.preventDefault();
                if (!saveName.trim()) return;
                saveList.mutate(
                  { name: saveName.trim(), tickers: allTickers, years },
                  {
                    onSuccess: (saved) => {
                      setShowSaveForm(false);
                      setSaveName("");
                      // Navigate to the newly saved list
                      const firstTicker = allTickers[0];
                      window.location.href = `/${firstTicker}/comparar?listId=${saved.id}`;
                    },
                  },
                );
              }}>
                <input
                  type="text"
                  className="auth-input"
                  placeholder={t("compare.list_name")}
                  value={saveName}
                  onChange={(event) => setSaveName(event.target.value)}
                  autoFocus
                />
                <div className="compare-save-modal-actions">
                  <button
                    type="submit"
                    className="auth-button"
                    disabled={!saveName.trim()}
                  >
                    {t("common.save")}
                  </button>
                  <button
                    type="button"
                    className="auth-button-secondary"
                    onClick={() => setShowSaveForm(false)}
                  >
                    {t("common.cancel")}
                  </button>
                </div>
              </form>
          </div>
        </div>
      )}

      {/* Auth modal — triggered when unauthenticated user tries to save or reorder */}
      {showAuthModal && (
        <AuthModal
          message={authModalMessage}
          onSuccess={() => {
            const wasTriggeredBySave = !authModalMessage;
            setShowAuthModal(false);
            setAuthModalMessage(undefined);
            queryClient.invalidateQueries({ queryKey: ["auth-user"] }).then(() => {
              if (wasTriggeredBySave) {
                setShowSaveForm(true);
              }
            });
          }}
          onClose={() => {
            setShowAuthModal(false);
            setAuthModalMessage(undefined);
          }}
        />
      )}
    </div>
  );
}

/* ── Row component ── */

function CompareRow({
  entry,
  index,
  isCurrentTicker,
  onRemove,
  columns,
  dragIndexRef,
  onReorder,
  totalRows,
  startGhost,
  stopGhost,
  isAuthenticated,
  onRequireAuth,
}: {
  entry: CompareEntry;
  index: number;
  isCurrentTicker: boolean;
  onRemove: (ticker: string) => void;
  columns: ColumnDef[];
  dragIndexRef: React.MutableRefObject<number | null>;
  onReorder: (from: number, to: number) => void;
  totalRows: number;
  startGhost: (element: HTMLElement, event: React.DragEvent) => void;
  stopGhost: () => void;
  isAuthenticated: boolean;
  onRequireAuth: () => void;
}) {
  const { t } = useTranslation();
  const { ticker, data, recent, pe, pfcf, isLoading, error } = entry;

  function handleDragStart(e: React.DragEvent) {
    dragIndexRef.current = index;
    e.dataTransfer.effectAllowed = "move";

    // Use the row as the ghost source
    const row = (e.target as HTMLElement).closest("tr");
    if (row) {
      startGhost(row, e);
      setTimeout(() => row.classList.add("compare-row-dragging"), 0);
    }
  }

  function handleDragEnd(e: React.DragEvent) {
    dragIndexRef.current = null;
    stopGhost();
    const row = (e.target as HTMLElement).closest("tr");
    if (row) row.classList.remove("compare-row-dragging");
    // Remove all drag-over indicators
    document.querySelectorAll(".compare-row-drag-over").forEach((el) =>
      el.classList.remove("compare-row-drag-over"),
    );
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    const row = (e.target as HTMLElement).closest("tr");
    if (row) row.classList.add("compare-row-drag-over");
  }

  function handleDragLeave(e: React.DragEvent) {
    const row = (e.target as HTMLElement).closest("tr");
    if (row) row.classList.remove("compare-row-drag-over");
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    stopGhost();
    const row = (e.target as HTMLElement).closest("tr");
    if (row) row.classList.remove("compare-row-drag-over");
    if (dragIndexRef.current !== null && dragIndexRef.current !== index) {
      if (!isAuthenticated) {
        dragIndexRef.current = null;
        onRequireAuth();
        return;
      }
      onReorder(dragIndexRef.current, index);
    }
  }

  const dragProps = totalRows > 1
    ? {
        onDragOver: handleDragOver,
        onDragLeave: handleDragLeave,
        onDrop: handleDrop,
      }
    : {};

  const dragHandle = totalRows > 1 ? (
    <td className="compare-drag-col">
      <span
        className="compare-drag-handle"
        draggable
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <DragIcon />
      </span>
    </td>
  ) : (
    <td className="compare-drag-col" />
  );

  const companyLink = `/${ticker}`;

  if (isLoading) {
    return (
      <tr {...dragProps}>
        {dragHandle}
        <td className="compare-sticky-col">
          <div className="compare-company-cell">
            <Link href={companyLink} className="compare-company-link">
              <span className="compare-company-ticker">{ticker}</span>
            </Link>
          </div>
        </td>
        {columns.map((col, index) => (
          <td key={col.key} className={GROUP_START_INDICES.has(index) ? "compare-group-separator" : undefined}>
            <div className="compare-loading-cell" />
          </td>
        ))}
        <td />
      </tr>
    );
  }

  if (error || !data) {
    return (
      <tr {...dragProps}>
        {dragHandle}
        <td className="compare-sticky-col">
          <div className="compare-company-cell">
            <Link href={companyLink} className="compare-company-link">
              <span className="compare-company-ticker">{ticker}</span>
            </Link>
          </div>
        </td>
        <td colSpan={columns.length}>
          <span className="compare-error-cell">
            {error?.message ?? t("compare.data_unavailable")}
          </span>
        </td>
        <td>
          {!isCurrentTicker && (
            <button className="compare-remove-btn" onClick={() => onRemove(ticker)} aria-label={`Remover ${ticker}`}>
              ×
            </button>
          )}
        </td>
      </tr>
    );
  }

  return (
    <tr {...dragProps}>
      {dragHandle}
      <td className="compare-sticky-col">
        <div className="compare-company-cell">
          <Link href={companyLink} className="compare-company-link">
            {data.logo && (
              <img
                className="compare-company-logo"
                src={logoUrl(data.ticker)}
                alt=""
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            )}
            <span className="compare-company-name" title={data.name}>{data.name}</span>
            <span className="compare-company-ticker">{ticker}</span>
          </Link>
        </div>
      </td>
      {columns.map((col, index) => {
        const rowData: CompareRowData = { quote: data, recent, pe, pfcf };
        const formatted = col.format(rowData);
        const className = GROUP_START_INDICES.has(index) ? "compare-group-separator" : undefined;
        return (
          <td key={col.key} className={className}>
            {formatted !== null ? formatted : <span className="compare-null">—</span>}
          </td>
        );
      })}
      <td>
        {!isCurrentTicker && (
          <button className="compare-remove-btn" onClick={() => onRemove(ticker)} aria-label={`Remover ${ticker}`}>
            ×
          </button>
        )}
      </td>
    </tr>
  );
}
