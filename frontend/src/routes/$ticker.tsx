import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { SearchBar } from "../components/SearchBar";
import { PE10Card, PE10CardLoading } from "../components/PE10Card";
import { ShareButtons } from "../components/ShareButtons";
import { usePE10 } from "../hooks/usePE10";
import { deriveForYears } from "../hooks/deriveForYears";

const DEFAULT_YEARS = 10;

export function TickerPage() {
  const { ticker } = useParams({ strict: false }) as { ticker: string };
  const upperTicker = ticker.toUpperCase();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [years, setYears] = useState(DEFAULT_YEARS);
  const { data: fullData, isLoading, error } = usePE10(upperTicker);

  const maxYears = fullData?.maxYearsAvailable ?? DEFAULT_YEARS;
  const effectiveYears = Math.min(years, maxYears);

  const derivedData = useMemo(
    () => fullData ? deriveForYears(fullData, effectiveYears) : null,
    [fullData, effectiveYears],
  );

  function handleSearch(newTicker: string) {
    queryClient.invalidateQueries({ queryKey: ["pe10", newTicker] });
    setYears(DEFAULT_YEARS);
    navigate({ to: "/$ticker", params: { ticker: newTicker } });
  }

  return (
    <div>
      <div className="back-home-wrapper">
        <Link to="/" className="back-home-link" aria-label="Início">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/><polyline points="9 21 9 14 15 14 15 21"/></svg>
        </Link>
      </div>
      <Link to="/" className="app-hero-title-link"><h1 className="app-hero-title">Sponda</h1></Link>
      <p className="app-hero-subtitle">Indicadores de empresas brasileiras para investidores em valor</p>

      <SearchBar onSearch={handleSearch} isLoading={isLoading} />

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

      <ShareButtons
        ticker={upperTicker}
        companyName={fullData?.name}
      />
    </div>
  );
}
