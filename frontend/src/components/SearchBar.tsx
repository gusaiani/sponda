import { useState, useRef, useEffect, FormEvent } from "react";
import { useTickerSearch } from "../hooks/useTickerSearch";
import type { TickerItem } from "../hooks/useTickers";
import { useTranslation } from "../i18n";
import "../styles/search.css";

interface SearchBarProps {
  onSearch: (ticker: string) => void;
  isLoading: boolean;
  autoFocus?: boolean;
}

export function SearchBar({ onSearch, isLoading, autoFocus }: SearchBarProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { results } = useTickerSearch(input);

  useEffect(() => {
    setSelectedIndex(-1);
  }, [results]);

  function select(item: TickerItem) {
    setInput(item.symbol);
    setShowDropdown(false);
    onSearch(item.symbol);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (selectedIndex >= 0 && selectedIndex < results.length) {
      select(results[selectedIndex]);
      return;
    }
    const ticker = input.trim().toUpperCase();
    if (ticker) {
      setShowDropdown(false);
      onSearch(ticker);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
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

  function handleChange(value: string) {
    setInput(value);
    setShowDropdown(value.trim().length > 0);
  }

  useEffect(() => {
    if (selectedIndex < 0 || !dropdownRef.current) return;
    const items = dropdownRef.current.children;
    if (items[selectedIndex]) {
      (items[selectedIndex] as HTMLElement).scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  return (
    <div className="search-container">
      <form className="search-form" role="search" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="search"
          className="search-input"
          aria-label={t("search.aria_label")}
          placeholder={t("search.placeholder")}
          value={input}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => input.trim() && setShowDropdown(true)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
          autoFocus={autoFocus}
        />
        <button
          type="submit"
          className="search-button"
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? (
            "..."
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          )}
        </button>

        {showDropdown && results.length > 0 && (
          <div className="search-dropdown" ref={dropdownRef}>
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
                  src={item.logo || "/favicon.svg"}
                  alt=""
                  loading="lazy"
                  onError={(e) => {
                    const image = e.target as HTMLImageElement;
                    if (image.src !== window.location.origin + "/favicon.svg") {
                      image.src = "/favicon.svg";
                    }
                  }}
                />
                <span className="search-dropdown-symbol">{item.symbol}</span>
                <span className="search-dropdown-name">
                  {item.name !== item.symbol ? item.name : ""}
                </span>
              </div>
            ))}
          </div>
        )}
      </form>
    </div>
  );
}
