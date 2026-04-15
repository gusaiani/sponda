"use client";

import { useState, useRef, useMemo, useEffect } from "react";
import { createPortal } from "react-dom";
import { useTickerSearch } from "../hooks/useTickerSearch";
import type { TickerItem } from "../hooks/useTickerSearch";
import { useFavorites } from "../hooks/useFavorites";
import { useTranslation } from "../i18n";
import { logoUrl } from "../utils/format";
import "../styles/homepage-cards.css";

export type AddFavoriteCardPosition = "first" | "last";

export function getAddFavoriteCardPosition({
  isAuthenticated,
  favoriteCount,
}: {
  isAuthenticated: boolean;
  favoriteCount: number;
}): AddFavoriteCardPosition {
  if (isAuthenticated && favoriteCount > 0) return "last";
  return "first";
}

interface AddFavoriteCardProps {
  onSelectTicker: (ticker: string) => void;
}

export function AddFavoriteCard({ onSelectTicker }: AddFavoriteCardProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { results: searchResults } = useTickerSearch(input);
  const { favoriteTickers } = useFavorites();
  const excludeSet = useMemo(() => new Set(favoriteTickers), [favoriteTickers]);

  const results = useMemo(
    () => searchResults.filter((t) => !excludeSet.has(t.symbol)).slice(0, 6),
    [searchResults, excludeSet],
  );

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
    onSelectTicker(item.symbol);
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
                <img
                  className="search-dropdown-logo"
                  src={logoUrl(item.symbol)}
                  alt=""
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
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
    <div
      className="hcc-card hcc-add-favorite-card"
      onClick={() => inputRef.current?.focus()}
    >
      <div className="hcc-add-favorite-prompt">
        <span className="hcc-add-favorite-star">☆</span>
        <span className="hcc-add-favorite-text">{t("favorites.add_card_title")}</span>
      </div>
      <div
        className="hcc-add-favorite-search"
        role="search"
        onClick={(event) => event.stopPropagation()}
      >
        <input
          ref={inputRef}
          type="search"
          className="hcc-add-favorite-input"
          aria-label={t("favorites.search_placeholder")}
          placeholder={t("favorites.search_placeholder")}
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
        <button
          type="button"
          className="hcc-add-favorite-search-button"
          aria-label={t("favorites.search_placeholder")}
          onClick={(event) => {
            event.preventDefault();
            if (results.length > 0) {
              select(results[selectedIndex >= 0 ? selectedIndex : 0]);
              return;
            }
            inputRef.current?.focus();
          }}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>
      </div>
      {dropdown}
    </div>
  );
}
