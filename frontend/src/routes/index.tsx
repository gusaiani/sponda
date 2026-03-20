import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { SearchBar } from "../components/SearchBar";
import { PopularCompanies } from "../components/PopularCompanies";
import { ShareButtons } from "../components/ShareButtons";
import { FontPickerLogo } from "../components/FontPickerLogo";

export function HomePage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  function handleSearch(newTicker: string) {
    queryClient.invalidateQueries({ queryKey: ["pe10", newTicker] });
    navigate({ to: "/$ticker", params: { ticker: newTicker } });
  }

  return (
    <div>
      <Link to="/" className="app-hero-title-link">
        <FontPickerLogo />
      </Link>
      <p className="app-hero-subtitle">Indicadores de empresas brasileiras para investidores em valor</p>

      <SearchBar onSearch={handleSearch} isLoading={false} autoFocus />

      <PopularCompanies />

      <ShareButtons />
    </div>
  );
}
