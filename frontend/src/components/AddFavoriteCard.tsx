"use client";

import { useState, useRef, useMemo, useEffect } from "react";
import { createPortal } from "react-dom";
import Fuse from "fuse.js";
import { useTickers, type TickerItem } from "../hooks/useTickers";
import { useFavorites } from "../hooks/useFavorites";
import { useAuth } from "../hooks/useAuth";
import { useQueryClient } from "@tanstack/react-query";
import { AuthModal } from "./AuthModal";
import "../styles/homepage-cards.css";

const MAX_FAVORITES_FOR_PLACEHOLDER = 3;

export function shouldShowAddFavoriteCard(
  isAuthenticated: boolean,
  favoriteCount: number,
): boolean {
  if (!isAuthenticated) return true;
  return favoriteCount >= 1 && favoriteCount <= MAX_FAVORITES_FOR_PLACEHOLDER;
}

export function AddFavoriteCard() {
  const [input, setInput] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [pendingTicker, setPendingTicker] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: allTickers = [] } = useTickers();
  const { isAuthenticated } = useAuth();
  const { favoriteTickers, toggleFavorite } = useFavorites();
  const queryClient = useQueryClient();
  const excludeSet = useMemo(() => new Set(favoriteTickers), [favoriteTickers]);

  const tickers = useMemo(
    () => allTickers.filter((t) => !excludeSet.has(t.symbol)),
    [allTickers, excludeSet],
  );

  const fuse = useMemo(
    () =>
      new Fuse(tickers, {
        keys: [
          { name: "symbol", weight: 2 },
          { name: "name", weight: 1 },
        ],
        threshold: 0.35,
      }),
    [tickers],
  );

  const results = useMemo(() => {
    if (!input.trim()) return [];
    return fuse.search(input, { limit: 6 }).map((r) => r.item);
  }, [fuse, input]);

  useEffect(() => {
    setSelectedIndex(-1);
  }, [results]);

  function updateDropdownPos() {
    if (!inputRef.current) return;
    const rect = inputRef.current.getBoundingClientRect();
    setDropdownPos({
      top: rect.bottom + window.scrollY,
      left: rect.left + window.scrollX,
      width: Math.max(rect.width, 250),
    });
  }

  function select(item: TickerItem) {
    setInput("");
    setShowDropdown(false);
    if (!isAuthenticated) {
      setPendingTicker(item.symbol);
      setShowAuthModal(true);
      return;
    }
    toggleFavorite(item.symbol);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < results.length) {
        select(results[selectedIndex]);
      }
      return;
    }
    if (!showDropdown || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => (i < results.length - 1 ? i + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => (i > 0 ? i - 1 : results.length - 1));
    } else if (e.key === "Escape") {
      setShowDropdown(false);
    }
  }

  useEffect(() => {
    if (selectedIndex < 0 || !dropdownRef.current) return;
    const items = dropdownRef.current.children;
    if (items[selectedIndex]) {
      (items[selectedIndex] as HTMLElement).scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  function openDropdown() {
    updateDropdownPos();
    setShowDropdown(true);
  }

  const dropdown =
    showDropdown && results.length > 0
      ? createPortal(
          <div
            className="compare-add-dropdown"
            ref={dropdownRef}
            style={{
              position: "absolute",
              top: dropdownPos.top,
              left: dropdownPos.left,
              width: dropdownPos.width,
            }}
          >
            {results.map((item, i) => (
              <div
                key={item.symbol}
                className={`search-dropdown-item ${i === selectedIndex ? "search-dropdown-item--active" : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  select(item);
                }}
                onMouseEnter={() => setSelectedIndex(i)}
              >
                {item.logo && (
                  <img
                    className="search-dropdown-logo"
                    src={item.logo}
                    alt=""
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                )}
                <span className="search-dropdown-symbol">{item.symbol}</span>
                <span className="search-dropdown-name">
                  {item.name !== item.symbol ? item.name : ""}
                </span>
              </div>
            ))}
          </div>,
          document.body,
        )
      : null;

  return (
    <div className="hcc-card hcc-add-favorite-card">
      <div className="hcc-add-favorite-prompt">
        <span className="hcc-add-favorite-star">☆</span>
        <span className="hcc-add-favorite-text">Adicione favoritas</span>
      </div>
      <input
        ref={inputRef}
        type="text"
        className="hcc-add-favorite-input"
        placeholder="Buscar empresa..."
        value={input}
        onChange={(e) => {
          setInput(e.target.value);
          if (e.target.value.trim().length > 0) {
            openDropdown();
          } else {
            setShowDropdown(false);
          }
        }}
        onKeyDown={handleKeyDown}
        onFocus={() => {
          if (input.trim()) openDropdown();
        }}
        onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
      />
      {dropdown}

      {showAuthModal && (
        <AuthModal
          onSuccess={() => {
            setShowAuthModal(false);
            queryClient.invalidateQueries({ queryKey: ["auth-user"] }).then(() => {
              if (pendingTicker) {
                toggleFavorite(pendingTicker);
                setPendingTicker(null);
              }
            });
          }}
          onClose={() => {
            setShowAuthModal(false);
            setPendingTicker(null);
          }}
        />
      )}
    </div>
  );
}
