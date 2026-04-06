import { useState, useEffect, useRef } from "react";

export interface TickerItem {
  symbol: string;
  name: string;
  sector: string;
  type: string;
  logo: string;
}

const DEBOUNCE_MS = 300;

async function searchTickers(query: string): Promise<TickerItem[]> {
  const response = await fetch(`/api/tickers/search/?q=${encodeURIComponent(query)}`, {
    credentials: "include",
  });
  if (!response.ok) return [];
  return response.json();
}

export function useTickerSearch(query: string) {
  const [results, setResults] = useState<TickerItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 1) {
      setResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);

    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const data = await searchTickers(trimmed);
        if (!controller.signal.aborted) {
          setResults(data);
          setIsSearching(false);
        }
      } catch {
        if (!controller.signal.aborted) {
          setIsSearching(false);
        }
      }
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      abortRef.current?.abort();
    };
  }, [query]);

  return { results, isSearching };
}
