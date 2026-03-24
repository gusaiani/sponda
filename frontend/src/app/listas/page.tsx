"use client";

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSavedLists, SavedListEntry } from "../../hooks/useSavedLists";
import { useAuth } from "../../hooks/useAuth";
import { useTickers, TickerItem } from "../../hooks/useTickers";
import { SavedListCard } from "../../components/SavedLists";

export default function AllListsPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { lists, isLoading, reorderLists } = useSavedLists();
  const { data: allTickers = [] } = useTickers();
  const [localOrder, setLocalOrder] = useState<SavedListEntry[] | null>(null);
  const dragIndexRef = useRef<number | null>(null);

  const tickerMap = useMemo(() => {
    const map = new Map<string, TickerItem>();
    for (const ticker of allTickers) map.set(ticker.symbol, ticker);
    return map;
  }, [allTickers]);

  if (authLoading || isLoading) {
    return (
      <div className="saved-lists-page">
        <p className="saved-lists-page-loading">Carregando…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="saved-lists-page">
        <h1 className="saved-lists-page-title">Acesso restrito</h1>
        <p className="saved-lists-page-text">
          Você precisa estar logado para ver suas listas.
        </p>
        <p className="auth-link">
          <Link href="/login">Fazer login</Link>
        </p>
      </div>
    );
  }

  const displayedLists = localOrder ?? lists;

  function handleDragStart(index: number) {
    dragIndexRef.current = index;
  }

  function handleDragOver(event: React.DragEvent, _index: number) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }

  function handleDrop(targetIndex: number) {
    const sourceIndex = dragIndexRef.current;
    if (sourceIndex === null || sourceIndex === targetIndex) return;

    const reordered = [...displayedLists];
    const [moved] = reordered.splice(sourceIndex, 1);
    reordered.splice(targetIndex, 0, moved);

    setLocalOrder(reordered);
    dragIndexRef.current = null;

    const orderedIds = reordered.map((list) => list.id);
    reorderLists.mutate(orderedIds);
  }

  return (
    <div className="saved-lists-page">
      <Link href="/" className="auth-logo-link">
        <span className="auth-logo">SPONDA</span>
      </Link>
      <h1 className="saved-lists-page-title">Suas Listas</h1>
      <p className="saved-lists-page-hint">
        Arraste para reordenar. As 3 primeiras aparecem na página inicial.
      </p>

      {displayedLists.length === 0 ? (
        <p className="saved-lists-page-text">Nenhuma lista salva.</p>
      ) : (
        <div className="saved-lists-page-list">
          {displayedLists.map((list, index) => (
            <div
              key={list.id}
              className="saved-lists-page-item"
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={(event) => handleDragOver(event, index)}
              onDrop={() => handleDrop(index)}
            >
              <span className="saved-lists-page-drag-handle">⠿</span>
              <SavedListCard list={list} tickerMap={tickerMap} />
            </div>
          ))}
        </div>
      )}

      <p className="auth-link" style={{ marginTop: "2rem" }}>
        <Link href="/">Voltar para a página inicial</Link>
      </p>
    </div>
  );
}
