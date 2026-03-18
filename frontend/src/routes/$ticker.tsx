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
