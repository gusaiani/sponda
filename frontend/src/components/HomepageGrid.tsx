"use client";

import { useState, useRef, useCallback, DragEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { useFavorites } from "../hooks/useFavorites";
import { useSavedLists } from "../hooks/useSavedLists";
import { useCompareData } from "../hooks/useCompareData";
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
import { useTickers } from "../hooks/useTickers";
import { useMemo } from "react";
import "../styles/homepage-cards.css";

const DEFAULT_TICKERS = [
  "PETR4", "VALE3", "ITUB4", "WEGE3",
  "ABEV3", "BBAS3", "RENT3", "SUZB3",
];

async function fetchHomepageLayout(): Promise<LayoutItem[] | null> {
  const response = await fetch("/api/auth/homepage-layout/", {
    credentials: "include",
  });
  if (!response.ok) return null;
  const data = await response.json();
  return data.layout;
}

export function HomepageGrid() {
  const { isAuthenticated } = useAuth();
  const { favoriteTickers, isFavorite, toggleFavorite } = useFavorites();
  const { lists } = useSavedLists();
  const { data: allTickers = [] } = useTickers();
  const queryClient = useQueryClient();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [pendingFavoriteTicker, setPendingFavoriteTicker] = useState<string | null>(null);

  const logoMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of allTickers) {
      if (t.logo) map.set(t.symbol, t.logo);
    }
    return map;
  }, [allTickers]);
  const [dragSourceIndex, setDragSourceIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const dragCounter = useRef<Map<number, number>>(new Map());

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

  const showPlaceholder = shouldShowAddFavoriteCard(isAuthenticated, favoriteTickers.length);
  const tickers = isAuthenticated && favoriteTickers.length > 0
    ? favoriteTickers.slice(0, 8)
    : DEFAULT_TICKERS.slice(0, showPlaceholder ? 7 : 8);

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
    setDragSourceIndex(index);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(index));
  }, []);

  const handleDragEnd = useCallback(() => {
    setDragSourceIndex(null);
    setDragOverIndex(null);
    dragCounter.current.clear();
  }, []);

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

      setDragSourceIndex(null);
      setDragOverIndex(null);
      dragCounter.current.clear();

      if (isNaN(sourceIndex) || sourceIndex === targetIndex) return;

      const newLayout = moveItem(activeLayout, sourceIndex, targetIndex);
      setLocalLayout(newLayout);

      if (isAuthenticated) {
        saveLayoutMutation.mutate(newLayout);
      } else {
        setShowAuthModal(true);
      }
    },
    [activeLayout, isAuthenticated, saveLayoutMutation],
  );

  const handleFavoriteSelect = useCallback((ticker: string) => {
    if (isAuthenticated) {
      if (!isFavorite(ticker)) {
        toggleFavorite(ticker);
      }
    } else {
      setPendingFavoriteTicker(ticker);
      setShowAuthModal(true);
    }
  }, [isAuthenticated, isFavorite, toggleFavorite]);

  const handleAuthSuccess = useCallback(async () => {
    setShowAuthModal(false);
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

  return (
    <section className="hcc-section">
      <div className="homepage-grid">
        {activeLayout.map((item, index) => {
          const isSpan2 = item.type === "list";
          const isDragging = dragSourceIndex === index;
          const isDragOver = dragOverIndex === index && dragSourceIndex !== index;

          const classNames = [
            "homepage-grid-item",
            isSpan2 ? "homepage-grid-item--span-2" : "",
            isDragging ? "homepage-grid-item--dragging" : "",
            isDragOver ? "homepage-grid-item--drag-over" : "",
          ]
            .filter(Boolean)
            .join(" ");

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
              {item.type === "ticker" ? (
                <TickerGridItem ticker={item.id} compareDataMap={compareDataMap} logoMap={logoMap} />
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
          onClose={() => setShowAuthModal(false)}
        />
      )}
    </section>
  );
}

interface TickerGridItemProps {
  ticker: string;
  compareDataMap: Map<string, { data: import("../hooks/usePE10").QuoteResult | null; isLoading: boolean }>;
  logoMap: Map<string, string>;
}

function TickerGridItem({ ticker, compareDataMap, logoMap }: TickerGridItemProps) {
  const entry = compareDataMap.get(ticker);
  return (
    <CompanyCard
      data={entry?.data ?? null}
      isLoading={entry?.isLoading ?? true}
      logoOverride={logoMap.get(ticker)}
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
