import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { SearchBar } from "../components/SearchBar";
import { PE10Card, PE10CardLoading } from "../components/PE10Card";
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
      <p className="app-hero-subtitle">Indicadores de empresas brasileiras para investidores em valor</p>

      <SearchBar onSearch={handleSearch} isLoading={isLoading} />

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
