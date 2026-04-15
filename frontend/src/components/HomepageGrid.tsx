"use client";

import { useState, useRef, useCallback, useEffect, DragEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useFavorites } from "../hooks/useFavorites";
import { useSavedLists } from "../hooks/useSavedLists";
import { useCompareData } from "../hooks/useCompareData";
import { useDragGhost } from "../hooks/useDragGhost";
import {
  LayoutItem,
  buildDefaultLayout,
  mergeLayoutWithData,
  moveItem,
} from "../utils/homepageLayout";
import { csrfHeaders } from "../utils/csrf";
import { CompanyCard } from "./HomepageCompanyCards";
import { ListCard } from "./ListCard";
import { AddFavoriteCard, shouldShowAddFavoriteCard } from "./AddFavoriteCard";
import { AuthModal } from "./AuthModal";
import { useRegion } from "../hooks/useRegion";
import { useTranslation } from "../i18n";
import { getDefaultTickers } from "../utils/suggestedCompanies";
import { useMemo } from "react";
import "../styles/homepage-cards.css";
import "../styles/share-dropdown.css";

export function getGridItemClassNames(
  isSpan2: boolean,
  isDragging: boolean,
  isDragOver: boolean,
): string {
  return [
    "homepage-grid-item",
    isSpan2 ? "homepage-grid-item--span-2" : "",
    isDragging ? "homepage-grid-item--dragging" : "",
    isDragOver ? "homepage-grid-item--drag-over" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

const UNVERIFIED_HOMEPAGE_TICKER_LIMIT = 8;
const DEFAULT_TICKER_COUNT_WITH_PLACEHOLDER = 7;
const DEFAULT_TICKER_COUNT = 8;

export function getHomepageTickers({
  isAuthenticated,
  isVerified,
  favoriteTickers,
  defaultTickers,
  showPlaceholder,
}: {
  isAuthenticated: boolean;
  isVerified: boolean;
  favoriteTickers: string[];
  defaultTickers: string[];
  showPlaceholder: boolean;
}): string[] {
  if (isAuthenticated && favoriteTickers.length > 0) {
    if (isVerified) return favoriteTickers;
    return favoriteTickers.slice(0, UNVERIFIED_HOMEPAGE_TICKER_LIMIT);
  }
  const defaultLimit = showPlaceholder
    ? DEFAULT_TICKER_COUNT_WITH_PLACEHOLDER
    : DEFAULT_TICKER_COUNT;
  return defaultTickers.slice(0, defaultLimit);
}

function ShareCardIcon() {
  return (
    <svg
      className="homepage-grid-share-icon"
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  );
}

function DragHandleIcon() {
  return (
    <svg
      className="homepage-grid-drag-icon"
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="currentColor"
      aria-hidden="true"
    >
      <circle cx="4" cy="2" r="1.2" />
      <circle cx="8" cy="2" r="1.2" />
      <circle cx="4" cy="6" r="1.2" />
      <circle cx="8" cy="6" r="1.2" />
      <circle cx="4" cy="10" r="1.2" />
      <circle cx="8" cy="10" r="1.2" />
    </svg>
  );
}

async function fetchHomepageLayout(): Promise<LayoutItem[] | null> {
  const response = await fetch("/api/auth/homepage-layout/", {
    credentials: "include",
  });
  if (!response.ok) return null;
  const data = await response.json();
  return data.layout;
}

function CardShareDropdown({ itemType, itemId, lists }: { itemType: string; itemId: string; lists: { id: number; name: string; tickers: string[] }[] }) {
  const { t, locale } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  let path: string;
  if (itemType === "ticker") {
    path = `/${locale}/${itemId}`;
  } else {
    const list = lists.find((l) => String(l.id) === itemId);
    path = list ? `/${locale}/${list.tickers[0]}/comparar?listId=${list.id}` : `/${locale}`;
  }

  const url = `https://sponda.capital${path}`;
  const text = itemType === "ticker"
    ? t("share.text_with_ticker", { name: itemId })
    : t("share.text_without_ticker");
  const encodedUrl = encodeURIComponent(url);
  const encodedText = encodeURIComponent(text);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setCopied(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => {
      setCopied(false);
      setIsOpen(false);
    }, 1200);
  }, [url]);

  return (
    <div className="homepage-grid-share-wrapper" ref={menuRef}>
      <button
        className="homepage-grid-share-handle"
        onClick={(event) => {
          event.stopPropagation();
          event.preventDefault();
          setIsOpen(!isOpen);
          setCopied(false);
        }}
        aria-label={t("share.label")}
      >
        <ShareCardIcon />
      </button>
      {isOpen && (
        <div className="share-dropdown-menu homepage-grid-share-menu" onClick={(event) => event.stopPropagation()}>
          <a
            className="share-dropdown-option"
            href={`https://x.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setIsOpen(false)}
          >
            <svg viewBox="0 0 24 24" fill="#000000" className="share-dropdown-icon">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
            </svg>
            <span>X / Twitter</span>
          </a>
          <a
            className="share-dropdown-option"
            href={`https://wa.me/?text=${encodedText}%20${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setIsOpen(false)}
          >
            <svg viewBox="0 0 24 24" fill="#25D366" className="share-dropdown-icon">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            <span>WhatsApp</span>
          </a>
          <a
            className="share-dropdown-option"
            href={`https://t.me/share/url?url=${encodedUrl}&text=${encodedText}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setIsOpen(false)}
          >
            <svg viewBox="0 0 24 24" fill="#26A5E4" className="share-dropdown-icon">
              <path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
            </svg>
            <span>Telegram</span>
          </a>
          <a
            className="share-dropdown-option"
            href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setIsOpen(false)}
          >
            <svg viewBox="0 0 24 24" fill="#0A66C2" className="share-dropdown-icon">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
            </svg>
            <span>LinkedIn</span>
          </a>
          <button
            className="share-dropdown-option"
            onClick={handleCopy}
          >
            {copied ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" className="share-dropdown-icon">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="#5570a0" strokeWidth="1.5" className="share-dropdown-icon">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
              </svg>
            )}
            <span>{copied ? t("share.copied") : t("share.copy_link")}</span>
          </button>
        </div>
      )}
    </div>
  );
}

export function HomepageGrid() {
  const { t } = useTranslation();
  const { user, isAuthenticated } = useAuth();
  const isVerified = user?.email_verified ?? false;
  const { favoriteTickers, isFavorite, toggleFavorite } = useFavorites();
  const { lists } = useSavedLists();
  const region = useRegion();
  const queryClient = useQueryClient();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authModalMessage, setAuthModalMessage] = useState<string | undefined>(undefined);
  const [pendingFavoriteTicker, setPendingFavoriteTicker] = useState<string | null>(null);

  const [dragSourceIndex, setDragSourceIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const dragCounter = useRef<Map<number, number>>(new Map());
  const { startGhost, stopGhost } = useDragGhost();

  const { data: savedLayout } = useQuery({
    queryKey: ["homepage-layout"],
    queryFn: fetchHomepageLayout,
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });

  const saveLayoutMutation = useMutation({
    mutationFn: async (layout: LayoutItem[]) => {
      const response = await fetch("/api/auth/homepage-layout/", {
        method: "PUT",
        headers: csrfHeaders(),
        credentials: "include",
        body: JSON.stringify({ layout }),
      });
      if (!response.ok) throw new Error("Failed to save layout");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["homepage-layout"] });
    },
  });

  const defaultTickers = getDefaultTickers(region);
  const showPlaceholder = shouldShowAddFavoriteCard(isAuthenticated, favoriteTickers.length);
  const tickers = getHomepageTickers({
    isAuthenticated,
    isVerified,
    favoriteTickers,
    defaultTickers,
    showPlaceholder,
  });

  const layout = useMemo(() => {
    if (savedLayout) {
      return mergeLayoutWithData(savedLayout, tickers, lists);
    }
    return buildDefaultLayout(tickers, lists);
  }, [savedLayout, tickers, lists]);

  const [localLayout, setLocalLayout] = useState<LayoutItem[] | null>(null);
  const activeLayout = localLayout ?? layout;

  // Keep localLayout in sync when layout changes from server
  const layoutKey = JSON.stringify(layout);
  const prevLayoutKeyRef = useRef(layoutKey);
  if (layoutKey !== prevLayoutKeyRef.current) {
    prevLayoutKeyRef.current = layoutKey;
    setLocalLayout(null);
  }

  const tickersInLayout = useMemo(
    () => activeLayout.filter((item) => item.type === "ticker").map((item) => item.id),
    [activeLayout],
  );

  const compareEntries = useCompareData(tickersInLayout, 10);

  const compareDataMap = useMemo(() => {
    const map = new Map<string, (typeof compareEntries)[number]>();
    for (const entry of compareEntries) {
      map.set(entry.ticker, entry);
    }
    return map;
  }, [compareEntries]);

  const handleDragStart = useCallback((event: DragEvent, index: number) => {
    const element = event.currentTarget as HTMLElement;
    startGhost(element, event);
    setDragSourceIndex(index);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(index));
  }, [startGhost]);

  const handleDragEnd = useCallback(() => {
    stopGhost();
    setDragSourceIndex(null);
    setDragOverIndex(null);
    dragCounter.current.clear();
  }, [stopGhost]);

  const handleDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const handleDragEnter = useCallback((event: DragEvent, index: number) => {
    event.preventDefault();
    const currentCount = dragCounter.current.get(index) ?? 0;
    dragCounter.current.set(index, currentCount + 1);
    setDragOverIndex(index);
  }, []);

  const handleDragLeave = useCallback((_event: DragEvent, index: number) => {
    const currentCount = dragCounter.current.get(index) ?? 0;
    const newCount = currentCount - 1;
    dragCounter.current.set(index, newCount);
    if (newCount <= 0) {
      dragCounter.current.delete(index);
      setDragOverIndex((current) => (current === index ? null : current));
    }
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent, targetIndex: number) => {
      event.preventDefault();
      const sourceIndex = parseInt(event.dataTransfer.getData("text/plain"), 10);

      stopGhost();
      setDragSourceIndex(null);
      setDragOverIndex(null);
      dragCounter.current.clear();

      if (isNaN(sourceIndex) || sourceIndex === targetIndex) return;

      const newLayout = moveItem(activeLayout, sourceIndex, targetIndex);
      setLocalLayout(newLayout);

      if (isAuthenticated) {
        saveLayoutMutation.mutate(newLayout);
      } else {
        setAuthModalMessage(
          t("homepage.auth_save_layout"),
        );
        setShowAuthModal(true);
      }
    },
    [activeLayout, isAuthenticated, saveLayoutMutation, stopGhost],
  );

  const handleFavoriteSelect = useCallback((ticker: string) => {
    if (isAuthenticated) {
      if (!isFavorite(ticker)) {
        toggleFavorite(ticker);
      }
    } else {
      setPendingFavoriteTicker(ticker);
      setAuthModalMessage(undefined);
      setShowAuthModal(true);
    }
  }, [isAuthenticated, isFavorite, toggleFavorite]);

  const handleAuthSuccess = useCallback(async () => {
    setShowAuthModal(false);
    setAuthModalMessage(undefined);
    const ticker = pendingFavoriteTicker;
    setPendingFavoriteTicker(null);

    // Refresh auth state and favorites after login/signup
    await queryClient.invalidateQueries({ queryKey: ["auth-user"] });
    await queryClient.invalidateQueries({ queryKey: ["favorites"] });
    await queryClient.invalidateQueries({ queryKey: ["homepage-layout"] });

    if (ticker) {
      // Refetch favorites to check if ticker is already there
      const freshFavorites = await queryClient.fetchQuery<Array<{ ticker: string }>>({
        queryKey: ["favorites"],
        staleTime: 0,
      });
      const alreadyFavorited = freshFavorites.some(
        (favorite) => favorite.ticker === ticker.toUpperCase(),
      );
      if (!alreadyFavorited) {
        toggleFavorite(ticker);
      }
    }
  }, [queryClient, pendingFavoriteTicker, toggleFavorite]);

  const handleCloseAuthModal = useCallback(() => {
    setShowAuthModal(false);
    setAuthModalMessage(undefined);
  }, []);

  return (
    <section className="hcc-section">
      <div className="homepage-grid">
        {activeLayout.map((item, index) => {
          const isSpan2 = item.type === "list";
          const isDragging = dragSourceIndex === index;
          const isDragOver = dragOverIndex === index && dragSourceIndex !== index;

          const classNames = getGridItemClassNames(isSpan2, isDragging, isDragOver);

          return (
            <div
              key={`${item.type}:${item.id}`}
              className={classNames}
              draggable
              onDragStart={(event) => handleDragStart(event, index)}
              onDragEnd={handleDragEnd}
              onDragOver={handleDragOver}
              onDragEnter={(event) => handleDragEnter(event, index)}
              onDragLeave={(event) => handleDragLeave(event, index)}
              onDrop={(event) => handleDrop(event, index)}
            >
              <span className="homepage-grid-card-actions">
                <CardShareDropdown itemType={item.type} itemId={item.id} lists={lists} />
                <span className="homepage-grid-drag-handle">
                  <DragHandleIcon />
                </span>
              </span>
              {item.type === "ticker" ? (
                <TickerGridItem ticker={item.id} compareDataMap={compareDataMap} />
              ) : (
                <ListGridItem listId={item.id} lists={lists} />
              )}
            </div>
          );
        })}
        {showPlaceholder && (
          <div className="homepage-grid-item homepage-grid-item--no-drag">
            <AddFavoriteCard onSelectTicker={handleFavoriteSelect} />
          </div>
        )}
      </div>

      {showAuthModal && (
        <AuthModal
          onSuccess={handleAuthSuccess}
          onClose={handleCloseAuthModal}
          message={authModalMessage}
        />
      )}
    </section>
  );
}

interface TickerGridItemProps {
  ticker: string;
  compareDataMap: Map<string, { data: import("../hooks/usePE10").QuoteResult | null; isLoading: boolean }>;
}

function TickerGridItem({ ticker, compareDataMap }: TickerGridItemProps) {
  const entry = compareDataMap.get(ticker);
  return (
    <CompanyCard
      data={entry?.data ?? null}
      isLoading={entry?.isLoading ?? true}
    />
  );
}

interface ListGridItemProps {
  listId: string;
  lists: { id: number; name: string; tickers: string[]; years: number }[];
}

function ListGridItem({ listId, lists }: ListGridItemProps) {
  const list = lists.find((l) => String(l.id) === listId);
  if (!list) return null;
  return <ListCard listId={list.id} name={list.name} tickers={list.tickers} years={list.years} />;
}
