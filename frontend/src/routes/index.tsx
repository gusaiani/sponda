import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { SearchBar } from "../components/SearchBar";
import { PE10Card, PE10CardLoading } from "../components/PE10Card";
import { PE10Explainer } from "../components/PE10Explainer";
import { usePE10 } from "../hooks/usePE10";

export function HomePage() {
  const [ticker, setTicker] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { data, isLoading, error } = usePE10(ticker);

  function handleSearch(newTicker: string) {
    setTicker(newTicker);
    queryClient.invalidateQueries({ queryKey: ["quota"] });
  }

  return (
    <div>
      <h1 className="app-hero-title">Sponda</h1>
      <p className="app-hero-subtitle">PE10 para ações brasileiras</p>

      <SearchBar onSearch={handleSearch} isLoading={isLoading} />

      <PE10Explainer />

      {isLoading && <PE10CardLoading />}
      {data && !isLoading && <PE10Card data={data} />}
      {error && !isLoading && (
        <div className="pe10-card">
          <div className="pe10-error">{(error as Error).message}</div>
        </div>
      )}
    </div>
  );
}
