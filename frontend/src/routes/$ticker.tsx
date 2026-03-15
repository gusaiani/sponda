import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { SearchBar } from "../components/SearchBar";
import { PE10Card, PE10CardLoading } from "../components/PE10Card";
import { ShareButtons } from "../components/ShareButtons";
import { usePE10 } from "../hooks/usePE10";

export function TickerPage() {
  const { ticker } = useParams({ strict: false }) as { ticker: string };
  const upperTicker = ticker.toUpperCase();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data, isLoading, error } = usePE10(upperTicker);

  function handleSearch(newTicker: string) {
    queryClient.invalidateQueries({ queryKey: ["pe10", newTicker] });
    navigate({ to: "/$ticker", params: { ticker: newTicker } });
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

      <ShareButtons
        ticker={upperTicker}
        companyName={data?.name}
      />
    </div>
  );
}
