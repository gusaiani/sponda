import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { SearchBar } from "../components/SearchBar";
import { FavoriteCompanies } from "../components/FavoriteCompanies";
import { SavedLists } from "../components/SavedLists";
import { PopularCompanies } from "../components/PopularCompanies";
import { ShareButtons } from "../components/ShareButtons";
import { useAuth } from "../hooks/useAuth";

export function HomePage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  function handleSearch(newTicker: string) {
    queryClient.invalidateQueries({ queryKey: ["pe10", newTicker] });
    navigate({ to: "/$ticker", params: { ticker: newTicker } });
  }

  return (
    <div>
      <Link to="/" className="app-hero-title-link">
        <span className="app-hero-logo">SPONDA</span>
      </Link>
      <p className="app-hero-subtitle">Indicadores de empresas brasileiras para investidores em valor</p>

      <SearchBar onSearch={handleSearch} isLoading={false} autoFocus />

      {isAuthenticated && <FavoriteCompanies />}
      {isAuthenticated && <SavedLists />}

      <PopularCompanies />

      <ShareButtons />
    </div>
  );
}
