import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, Outlet, useNavigate, useParams, useLocation } from "@tanstack/react-router";
import { SearchBar } from "../components/SearchBar";
import { PE10Card, PE10CardLoading } from "../components/PE10Card";
import { MultiplesChart, MultiplesChartLoading } from "../components/MultiplesChart";
import { CompareTab } from "../components/CompareTab";
import { ShareButtons } from "../components/ShareButtons";
import { usePE10, fetchQuote } from "../hooks/usePE10";
import { useTickers } from "../hooks/useTickers";
import { useMultiplesHistory } from "../hooks/useMultiplesHistory";
import { deriveForYears } from "../hooks/deriveForYears";
import { getSectorPeers } from "../utils/subsector";
import "../styles/chart.css";

const DEFAULT_YEARS = 10;

type TabKey = "metrics" | "charts" | "compare";

const TAB_PATHS: Record<string, TabKey> = {
  graficos: "charts",
  comparar: "compare",
};

const TAB_TO_SUFFIX: Record<TabKey, string> = {
  metrics: "",
  charts: "/graficos",
  compare: "/comparar",
};

function resolveTab(pathname: string): TabKey {
  // Check path suffix: /<ticker>/graficos or /<ticker>/comparar
  const lastSegment = pathname.split("/").filter(Boolean).pop() ?? "";
  if (TAB_PATHS[lastSegment]) return TAB_PATHS[lastSegment];

  // Fallback: ?aba= query param (backwards compat)
  const params = new URLSearchParams(window.location.search);
  const aba = params.get("aba");
  if (aba && TAB_PATHS[aba]) return TAB_PATHS[aba];

  return "metrics";
}

export function TickerPage() {
  const { ticker } = useParams({ strict: false }) as { ticker: string };
  const upperTicker = ticker.toUpperCase();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [years, setYears] = useState(DEFAULT_YEARS);
  const [compareTickers, setCompareTickers] = useState<string[]>([]);
  const seededForTicker = useRef<string | null>(null);

  const activeTab = resolveTab(location.pathname);

  const { data: fullData, isLoading, error } = usePE10(upperTicker);
  const { data: allTickers } = useTickers();

  // Seed compare list with same-sector companies and prefetch their data
  useEffect(() => {
    if (seededForTicker.current === upperTicker) return;
    if (!allTickers?.length) return;
    if (!fullData) return; // wait for main ticker to load first

    const current = allTickers.find((t) => t.symbol === upperTicker);
    if (!current?.sector) {
      seededForTicker.current = upperTicker;
      return;
    }

    const sectorPeers = getSectorPeers(
      upperTicker,
      current.name,
      current.sector,
      allTickers,
    );

    setCompareTickers(sectorPeers);
    seededForTicker.current = upperTicker;

    // Prefetch peer data in background
    for (const peer of sectorPeers) {
      queryClient.prefetchQuery({
        queryKey: ["pe10", peer],
        queryFn: () => fetchQuote(peer),
        staleTime: 5 * 60 * 1000,
      });
    }
  }, [upperTicker, allTickers, fullData, queryClient]);

  // Lazy: only fetch when charts tab is active
  const {
    data: historyData,
    isLoading: historyLoading,
    error: historyError,
  } = useMultiplesHistory(upperTicker, activeTab === "charts");

  const maxYears = fullData?.maxYearsAvailable ?? DEFAULT_YEARS;
  const effectiveYears = Math.min(years, maxYears);

  // Dynamic page title (OG tags are injected server-side for crawlers)
  useEffect(() => {
    const companyName = fullData?.name;
    document.title = companyName
      ? `${upperTicker} ${companyName} — Sponda`
      : `${upperTicker} — Sponda`;
    return () => {
      document.title = "Sponda — Indicadores de Empresas Brasileiras para Investidores em Valor";
    };
  }, [upperTicker, fullData?.name]);

  const derivedData = useMemo(
    () => fullData ? deriveForYears(fullData, effectiveYears) : null,
    [fullData, effectiveYears],
  );

  function switchTab(tab: TabKey) {
    const path = `/${upperTicker}${TAB_TO_SUFFIX[tab]}`;
    navigate({ to: path });
  }

  function handleSearch(newTicker: string) {
    queryClient.invalidateQueries({ queryKey: ["pe10", newTicker] });
    queryClient.invalidateQueries({ queryKey: ["multiples-history", newTicker] });
    setYears(DEFAULT_YEARS);
    setCompareTickers([]);
    seededForTicker.current = null;
    navigate({ to: "/$ticker", params: { ticker: newTicker } });
  }

  return (
    <div>
      <nav className="back-home-wrapper" aria-label="Navegação">
        <Link to="/" className="back-home-link" aria-label="Voltar para a página inicial">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/><polyline points="9 21 9 14 15 14 15 21"/></svg>
        </Link>
      </nav>
      <Link to="/" className="app-hero-title-link">
        <span className="app-hero-logo">SPONDA</span>
      </Link>
      <p className="app-hero-subtitle">Indicadores de empresas brasileiras para investidores em valor</p>

      <SearchBar onSearch={handleSearch} isLoading={isLoading} />

      {/* Tabs */}
      {!isLoading && !error && (
        <div className="tabs-wrapper">
          <button
            className={`tab-pill ${activeTab === "metrics" ? "tab-pill-active" : ""}`}
            onClick={() => switchTab("metrics")}
          >
            Indicadores
          </button>
          <button
            className={`tab-pill ${activeTab === "charts" ? "tab-pill-active" : ""}`}
            onClick={() => switchTab("charts")}
          >
            Gráficos
          </button>
          <button
            className={`tab-pill ${activeTab === "compare" ? "tab-pill-active" : ""}`}
            onClick={() => switchTab("compare")}
          >
            Comparar
          </button>
        </div>
      )}

      {/* Metrics tab */}
      {activeTab === "metrics" && (
        <>
          {isLoading && <PE10CardLoading />}
          {derivedData && !isLoading && (
            <PE10Card
              data={derivedData}
              years={effectiveYears}
              maxYears={maxYears}
              onYearsChange={setYears}
            />
          )}
          {error && !isLoading && (
            <div className="pe10-card">
              <div className="pe10-error">{(error as Error).message}</div>
            </div>
          )}
        </>
      )}

      {/* Charts tab */}
      {activeTab === "charts" && (
        <>
          {historyLoading && <MultiplesChartLoading />}
          {historyData && !historyLoading && (
            <MultiplesChart
              data={historyData}
              company={{
                ticker: upperTicker,
                name: fullData?.name ?? upperTicker,
                logo: fullData?.logo ?? "",
              }}
            />
          )}
          {historyError && !historyLoading && (
            <div className="chart-container">
              <div className="chart-error">{(historyError as Error).message}</div>
            </div>
          )}
        </>
      )}

      {/* Compare tab */}
      {activeTab === "compare" && (
        <CompareTab
          currentTicker={upperTicker}
          years={effectiveYears}
          maxYears={maxYears}
          onYearsChange={setYears}
          extraTickers={compareTickers}
          onExtraTickersChange={setCompareTickers}
        />
      )}

      <ShareButtons
        ticker={upperTicker}
        companyName={fullData?.name}
      />
      <Outlet />
    </div>
  );
}
