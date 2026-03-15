import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { SearchBar } from "../components/SearchBar";
import { ShareButtons } from "../components/ShareButtons";

export function HomePage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  function handleSearch(newTicker: string) {
    queryClient.invalidateQueries({ queryKey: ["pe10", newTicker] });
    navigate({ to: "/$ticker", params: { ticker: newTicker } });
  }

  return (
    <div>
      <h1 className="app-hero-title">Sponda</h1>
      <p className="app-hero-subtitle">Indicadores de empresas brasileiras para investidores em valor</p>

      <SearchBar onSearch={handleSearch} isLoading={false} />

      <ShareButtons />
    </div>
  );
}
