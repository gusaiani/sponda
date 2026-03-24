import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { SearchBar } from "../components/SearchBar";
import { FavoriteCompanies } from "../components/FavoriteCompanies";
import { SavedLists } from "../components/SavedLists";
import { PopularCompanies } from "../components/PopularCompanies";
import { ShareButtons } from "../components/ShareButtons";
import { useAuth } from "../hooks/useAuth";
import "../styles/popular.css";

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
      {isAuthenticated && <hr className="favorites-separator" />}

      <PopularCompanies />

      <article className="homepage-explainer">
        <h2 className="homepage-explainer-title">Indicadores fundamentalistas ajustados pela inflação</h2>
        <p>
          O Sponda calcula indicadores de valuation e qualidade para todas as ações da B3,
          ajustados pela inflação (IPCA). Diferente do P/L convencional, que usa apenas o
          lucro dos últimos 12 meses, o <strong>PE10</strong> (também conhecido como
          Shiller PE ou CAPE) utiliza a média dos lucros dos últimos 10 anos, corrigidos pela
          inflação — reduzindo o efeito de ciclos econômicos sobre a avaliação.
        </p>
        <p>
          Além do PE10, o Sponda oferece o <strong>PFCF10</strong> (Preço sobre Fluxo de Caixa
          Livre ajustado), <strong>PEG</strong> (PE10 dividido pelo crescimento dos lucros),
          <strong>CAGR</strong> do lucro e do fluxo de caixa, e indicadores de
          <strong> alavancagem</strong> como Dívida/PL e Passivo/PL.
        </p>
        <p>
          Explore os indicadores de empresas como{" "}
          <Link to="/$ticker" params={{ ticker: "PETR4" }}>PETR4</Link>,{" "}
          <Link to="/$ticker" params={{ ticker: "VALE3" }}>VALE3</Link>,{" "}
          <Link to="/$ticker" params={{ ticker: "ITUB4" }}>ITUB4</Link>,{" "}
          <Link to="/$ticker" params={{ ticker: "WEGE3" }}>WEGE3</Link> e{" "}
          <Link to="/$ticker" params={{ ticker: "ABEV3" }}>ABEV3</Link> — ou
          busque qualquer ação da B3 na barra de pesquisa acima.
        </p>
      </article>

      <ShareButtons />
    </div>
  );
}
