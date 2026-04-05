import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useTickerSearch } from "../hooks/useTickerSearch";
import type { TickerItem } from "../hooks/useTickers";
import { useTranslation } from "../i18n";
import "../styles/compare.css";

interface Props {
  onAdd: (ticker: string) => void;
  excludeTickers: string[];
}

export function CompanySearchInput({ onAdd, excludeTickers }: Props) {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const excludeSet = new Set(excludeTickers);
  const { results: rawResults } = useTickerSearch(input);
  const results = rawResults.filter((t) => !excludeSet.has(t.symbol)).slice(0, 6);

  useEffect(() => {
    setSelectedIndex(-1);
  }, [results.length]);

  const updateDropdownPos = useCallback(() => {
    if (!inputRef.current) return;
    const rect = inputRef.current.getBoundingClientRect();
    setDropdownPos({
      top: rect.bottom + window.scrollY,
      left: rect.left + window.scrollX,
      width: Math.max(rect.width, 250),
    });
  }, []);

  function select(item: TickerItem) {
    setInput("");
    setShowDropdown(false);
    onAdd(item.symbol);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < results.length) {
        select(results[selectedIndex]);
      } else if (input.trim()) {
        const ticker = input.trim().toUpperCase();
        setInput("");
        setShowDropdown(false);
        onAdd(ticker);
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
                  src={item.logo || "/favicon.svg"}
                  alt=""
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
          </div>,
          document.body,
        )
      : null;

  return (
    <div className="compare-add-wrapper">
      <input
        ref={inputRef}
        type="text"
        className="compare-add-input"
        placeholder={t("compare.add_company")}
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
    </div>
  );
}
