"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useSavedLists, SavedListEntry } from "../../../hooks/useSavedLists";
import { useAuth } from "../../../hooks/useAuth";
import { useDragGhost } from "../../../hooks/useDragGhost";
import { SavedListCard } from "../../../components/SavedLists";
import { useTranslation } from "../../../i18n";

export default function AllListsPage() {
  const { t, locale } = useTranslation();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { lists, isLoading, reorderLists } = useSavedLists();
  const [localOrder, setLocalOrder] = useState<SavedListEntry[] | null>(null);
  const dragIndexRef = useRef<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [dragSourceIndex, setDragSourceIndex] = useState<number | null>(null);
  const { startGhost, stopGhost } = useDragGhost();

  if (authLoading || isLoading) {
    return (
      <div className="saved-lists-page">
        <p className="saved-lists-page-loading">{t("common.loading")}</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="saved-lists-page">
        <h1 className="saved-lists-page-title">{t("auth.restricted_access")}</h1>
        <p className="saved-lists-page-text">
          {t("lists.must_login")}
        </p>
        <p className="auth-link">
          <Link href={`/${locale}/login`}>{t("auth.do_login")}</Link>
        </p>
      </div>
    );
  }

  const displayedLists = localOrder ?? lists;

  function handleDragStart(index: number, event: React.DragEvent) {
    dragIndexRef.current = index;
    setDragSourceIndex(index);
    const element = event.currentTarget as HTMLElement;
    startGhost(element, event);
    event.dataTransfer.effectAllowed = "move";
  }

  function handleDragOver(event: React.DragEvent, index: number) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOverIndex(index);
  }

  function handleDragLeave(_event: React.DragEvent, index: number) {
    setDragOverIndex((current) => (current === index ? null : current));
  }

  function handleDragEnd() {
    stopGhost();
    setDragSourceIndex(null);
    setDragOverIndex(null);
    dragIndexRef.current = null;
  }

  function handleDrop(targetIndex: number) {
    const sourceIndex = dragIndexRef.current;
    stopGhost();
    setDragSourceIndex(null);
    setDragOverIndex(null);

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
      <Link href={`/${locale}`} className="auth-logo-link">
        <span className="auth-logo">SPONDA</span>
      </Link>
      <h1 className="saved-lists-page-title">{t("lists.page_title")}</h1>
      <p className="saved-lists-page-hint">
        {t("lists.page_hint")}
      </p>

      {displayedLists.length === 0 ? (
        <p className="saved-lists-page-text">{t("lists.no_lists")}</p>
      ) : (
        <div className="saved-lists-page-list">
          {displayedLists.map((list, index) => {
            const isDragging = dragSourceIndex === index;
            const isDragOver = dragOverIndex === index && dragSourceIndex !== index;

            const classNames = [
              "saved-lists-page-item",
              isDragging ? "saved-lists-page-item--dragging" : "",
              isDragOver ? "saved-lists-page-item--drag-over" : "",
            ]
              .filter(Boolean)
              .join(" ");

            return (
              <div
                key={list.id}
                className={classNames}
                draggable
                onDragStart={(event) => handleDragStart(index, event)}
                onDragEnd={handleDragEnd}
                onDragOver={(event) => handleDragOver(event, index)}
                onDragLeave={(event) => handleDragLeave(event, index)}
                onDrop={() => handleDrop(index)}
              >
                <span className="saved-lists-page-drag-handle">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
                    <circle cx="4" cy="2" r="1.2" />
                    <circle cx="8" cy="2" r="1.2" />
                    <circle cx="4" cy="6" r="1.2" />
                    <circle cx="8" cy="6" r="1.2" />
                    <circle cx="4" cy="10" r="1.2" />
                    <circle cx="8" cy="10" r="1.2" />
                  </svg>
                </span>
                <SavedListCard list={list} />
              </div>
            );
          })}
        </div>
      )}

      <p className="auth-link" style={{ marginTop: "2rem" }}>
        <Link href={`/${locale}`}>{t("auth.back_to_homepage")}</Link>
      </p>
    </div>
  );
}
