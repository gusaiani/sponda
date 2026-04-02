import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useCompareData, type CompareEntry } from "../hooks/useCompareData";
import { useSavedLists } from "../hooks/useSavedLists";
import { useAuth } from "../hooks/useAuth";
import { useFavorites } from "../hooks/useFavorites";
import { useDragGhost } from "../hooks/useDragGhost";
import { AuthModal } from "./AuthModal";
import { CompanySearchInput } from "./CompanySearchInput";
import { br } from "../utils/format";
import type { QuoteResult } from "../hooks/usePE10";
import "../styles/compare.css";

/* ── Column definitions ── */

interface ColumnDef {
  key: string;
  label: string;
  group: "endividamento" | "rentabilidade" | "valuation";
  format: (d: QuoteResult) => string | null;
  value: (d: QuoteResult) => number | null;
}

type SortDir = "asc" | "desc";
interface SortState {
  key: string;
  dir: SortDir;
}

export function getColumns(years: number): ColumnDef[] {
  const n = years;
  return [
    // Endividamento
    { key: "debtToEquity", label: "Dív/PL", group: "endividamento", format: (d) => d.debtToEquity !== null ? br(d.debtToEquity, 2) : null, value: (d) => d.debtToEquity },
    { key: "debtExLeaseToEquity", label: "Dív-Arr/PL", group: "endividamento", format: (d) => d.debtExLeaseToEquity !== null ? br(d.debtExLeaseToEquity, 2) : null, value: (d) => d.debtExLeaseToEquity },
    { key: "liabilitiesToEquity", label: "Pass/PL", group: "endividamento", format: (d) => d.liabilitiesToEquity !== null ? br(d.liabilitiesToEquity, 2) : null, value: (d) => d.liabilitiesToEquity },
    { key: "debtToAvgEarnings", label: `Dív/Lucro${n}`, group: "endividamento", format: (d) => d.debtToAvgEarnings !== null ? br(d.debtToAvgEarnings, 1) : null, value: (d) => d.debtToAvgEarnings },
    { key: "debtToAvgFCF", label: `Dív/FCL${n}`, group: "endividamento", format: (d) => d.debtToAvgFCF !== null ? br(d.debtToAvgFCF, 1) : null, value: (d) => d.debtToAvgFCF },
    { key: "currentRatio", label: "Liq. Corr.", group: "endividamento", format: (d) => d.currentRatio !== null ? br(d.currentRatio, 2) : null, value: (d) => d.currentRatio },
    // Rentabilidade
    { key: "roe", label: `ROE${n}`, group: "rentabilidade", format: (d) => d.roe !== null ? `${br(d.roe, 1)}%` : null, value: (d) => d.roe },
    { key: "priceToBook", label: "P/VPA", group: "rentabilidade", format: (d) => d.priceToBook !== null ? br(d.priceToBook, 2) : null, value: (d) => d.priceToBook },
    // Valuation
    { key: "pe10", label: `P/L${n}`, group: "valuation", format: (d) => d.pe10 !== null ? br(d.pe10, 1) : null, value: (d) => d.pe10 },
    { key: "pfcf10", label: `P/FCL${n}`, group: "valuation", format: (d) => d.pfcf10 !== null ? br(d.pfcf10, 1) : null, value: (d) => d.pfcf10 },
    { key: "peg", label: `PEG${n}`, group: "valuation", format: (d) => d.peg !== null ? br(d.peg, 2) : null, value: (d) => d.peg },
    { key: "pfcfPeg", label: `PFCLG${n}`, group: "valuation", format: (d) => d.pfcfPeg !== null ? br(d.pfcfPeg, 2) : null, value: (d) => d.pfcfPeg },
    { key: "earningsCAGR", label: `CAGR L${n}`, group: "valuation", format: (d) => d.earningsCAGR !== null ? `${br(d.earningsCAGR, 1)}%` : null, value: (d) => d.earningsCAGR },
    { key: "fcfCAGR", label: `CAGR FCL${n}`, group: "valuation", format: (d) => d.fcfCAGR !== null ? `${br(d.fcfCAGR, 1)}%` : null, value: (d) => d.fcfCAGR },
  ];
}

const DEBT_COUNT = 6;
const RENT_COUNT = 2;
const VAL_COUNT = 6;

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
  const allTickers = [currentTicker, ...extraTickers];
  const entries = useCompareData(allTickers, years);
  const columns = getColumns(years);
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
      const va = a.data ? col.value(a.data) : null;
      const vb = b.data ? col.value(b.data) : null;
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
              <th colSpan={DEBT_COUNT}>Endividamento</th>
              <th colSpan={RENT_COUNT}>Rentabilidade</th>
              <th colSpan={VAL_COUNT}>Preço vs. Resultados</th>
              <th />
            </tr>
            {/* Column headers */}
            <tr>
              <th className="compare-drag-col" />
              <th className="compare-sticky-col">Empresa</th>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="compare-sortable-th"
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
                  setAuthModalMessage("Para reordenar as empresas, entre ou crie uma conta gratuita.");
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

      {/* Years slider — below table */}
      <div className="compare-slider-wrapper">
        <div className="years-slider">
          <div className="years-slider-track">
            <span className="years-slider-bound">1</span>
            <input
              type="range"
              className="years-slider-input"
              min={1}
              max={maxYears}
              value={years}
              onChange={(e) => onYearsChange(Number(e.target.value))}
            />
            <span className="years-slider-bound">{maxYears}</span>
          </div>
          <p className="years-slider-caption">
            Analisando os últimos <strong>{years} {years === 1 ? "ano" : "anos"}</strong>
          </p>
        </div>
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
              Renomear
            </button>
            <button
              className="compare-save-floating"
              onClick={() => {
                setSaveName(existingList.name + " (cópia)");
                setShowSaveForm(true);
              }}
            >
              Duplicar
            </button>
            <button
              className="compare-save-floating compare-save-floating-danger"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Apagar
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
              Salvar lista
            </button>
          </div>
        )
      )}

      {/* Rename modal */}
      {showRenameForm && existingList && (
        <div className="compare-save-overlay" onClick={() => setShowRenameForm(false)}>
          <div className="compare-save-modal" onClick={(event) => event.stopPropagation()}>
            <h3 className="compare-save-modal-title">Renomear lista</h3>
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
                placeholder="Novo nome"
                value={renameName}
                onChange={(event) => setRenameName(event.target.value)}
                autoFocus
              />
              <div className="compare-save-modal-actions">
                <button type="submit" className="auth-button" disabled={!renameName.trim()}>
                  Renomear
                </button>
                <button type="button" className="auth-button-secondary" onClick={() => setShowRenameForm(false)}>
                  Cancelar
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
            <h3 className="compare-save-modal-title">Apagar lista</h3>
            <p className="compare-save-modal-detail">
              Tem certeza que deseja apagar "{existingList.name}"?
            </p>
            <div className="compare-save-modal-actions">
              <button
                className="auth-button compare-delete-button"
                onClick={() => {
                  deleteList.mutate(existingList.id);
                  setShowDeleteConfirm(false);
                }}
              >
                Apagar
              </button>
              <button
                className="auth-button-secondary"
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancelar
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
              {existingList ? "Duplicar lista" : "Salvar lista"}
            </h3>
            <p className="compare-save-modal-detail">
              {allTickers.length} empresas · {years} {years === 1 ? "ano" : "anos"}
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
                  placeholder="Nome da lista"
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
                    Salvar
                  </button>
                  <button
                    type="button"
                    className="auth-button-secondary"
                    onClick={() => setShowSaveForm(false)}
                  >
                    Cancelar
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
  const { ticker, data, isLoading, error } = entry;

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
        {columns.map((col) => (
          <td key={col.key}>
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
            {error?.message ?? "Dados indisponíveis"}
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
                src={data.logo}
                alt=""
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            )}
            <span className="compare-company-name" title={data.name}>{data.name}</span>
            <span className="compare-company-ticker">{ticker}</span>
          </Link>
        </div>
      </td>
      {columns.map((col) => {
        const formatted = col.format(data);
        return (
          <td key={col.key}>
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
