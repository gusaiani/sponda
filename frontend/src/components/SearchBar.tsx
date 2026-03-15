import { useState, useRef, useMemo, useEffect, FormEvent } from "react";
import Fuse from "fuse.js";
import { useTickers, TickerItem } from "../hooks/useTickers";
import "../styles/search.css";

interface SearchBarProps {
  onSearch: (ticker: string) => void;
  isLoading: boolean;
}

export function SearchBar({ onSearch, isLoading }: SearchBarProps) {
  const [input, setInput] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: tickers = [] } = useTickers();

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
    return fuse.search(input, { limit: 8 }).map((r) => r.item);
  }, [fuse, input]);

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

  // Scroll selected item into view
  useEffect(() => {
    if (selectedIndex < 0 || !dropdownRef.current) return;
    const items = dropdownRef.current.children;
    if (items[selectedIndex]) {
      (items[selectedIndex] as HTMLElement).scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  return (
    <div className="search-container">
      <form className="search-form" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder="Ticker ou nome da empresa"
          value={input}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => input.trim() && setShowDropdown(true)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
        />
        <button
          type="submit"
          className="search-button"
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? "Buscando..." : "Buscar"}
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
          </div>
        )}
      </form>
    </div>
  );
}
