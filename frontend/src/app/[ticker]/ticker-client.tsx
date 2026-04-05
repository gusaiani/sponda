"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useParams, usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
const CompanyMetricsCard = dynamic(
  () => import("../../components/CompanyMetricsCard").then((mod) => mod.CompanyMetricsCard),
  { ssr: false }
);
const MultiplesChart = dynamic(
  () => import("../../components/MultiplesChart").then((mod) => mod.MultiplesChart),
  { ssr: false }
);

function CompanyMetricsCardLoading() {
  return (
    <div className="pe10-loading">
      <div className="pe10-loading-bar" />
      <div className="pe10-loading-bar-lg" />
      <div className="pe10-loading-bar-row">
        <div className="pe10-loading-bar-sm" />
        <div className="pe10-loading-bar-sm" />
        <div className="pe10-loading-bar-sm" />
      </div>
    </div>
  );
}

function MultiplesChartLoading() {
  return (
    <div className="chart-loading">
      <div className="chart-loading-bar" />
      <div className="chart-loading-bar-sm" />
    </div>
  );
}

const CompareTab = dynamic(
  () => import("../../components/CompareTab").then((mod) => mod.CompareTab),
  { ssr: false }
);
const FundamentalsTab = dynamic(
  () => import("../../components/FundamentalsTab").then((mod) => mod.FundamentalsTab),
  { ssr: false }
);
const CompanyAnalysis = dynamic(
  () => import("../../components/CompanyAnalysis").then((mod) => mod.CompanyAnalysis),
  { ssr: false }
);
import { FavoriteButton } from "../../components/FavoriteButton";
import { ShareButtons } from "../../components/ShareButtons";
import { usePE10, fetchQuote, type QuoteResult } from "../../hooks/usePE10";
import { useTickers } from "../../hooks/useTickers";
import { useMultiplesHistory } from "../../hooks/useMultiplesHistory";
import { deriveForYears } from "../../hooks/deriveForYears";
import { useSavedLists } from "../../hooks/useSavedLists";
import { logoUrl } from "../../utils/format";
import { getSectorPeers } from "../../utils/subsector";
import { useTranslation } from "../../i18n";

const DEFAULT_YEARS = 10;

import { resolveTab, buildTabPath, TAB_LABELS, type TabKey } from "../../utils/tabs";

interface TickerPageClientProps {
  initialData?: QuoteResult | null;
}

export function TickerPageClient({ initialData }: TickerPageClientProps) {
  const { t } = useTranslation();
  const { ticker: rawTicker } = useParams<{ ticker: string }>();
  const upperTicker = (rawTicker || "").toUpperCase();
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const [years, setYears] = useState(DEFAULT_YEARS);
  const [compareTickers, setCompareTickers] = useState<string[]>([]);
  const [activeListId, setActiveListId] = useState<number | null>(null);
  const seededForTicker = useRef<string | null>(null);

  const activeTab = resolveTab(pathname);

  const { data: fullData, isLoading, error } = usePE10(upperTicker, initialData ?? undefined);
  const { data: allTickers } = useTickers();
  const { lists } = useSavedLists();
  const currentTicker = allTickers?.find((t) => t.symbol === upperTicker);

  // Check for listId in URL search params (when opening a saved list)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const listIdParam = params.get("listId");
    if (!listIdParam) return;

    const listId = parseInt(listIdParam, 10);
    const savedList = lists.find((list) => list.id === listId);
    if (!savedList) return;

    const otherTickers = savedList.tickers.filter(
      (ticker) => ticker !== upperTicker
    );
    setCompareTickers(otherTickers);
    setYears(savedList.years);
    setActiveListId(listId);
    seededForTicker.current = upperTicker;
  }, [lists, upperTicker]);

  // Seed compare list with same-sector companies and prefetch their data
  useEffect(() => {
    if (seededForTicker.current === upperTicker) return;
    if (!allTickers?.length) return;
    if (!fullData) return;

    const current = allTickers.find((ticker) => ticker.symbol === upperTicker);
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

  const derivedData = useMemo(
    () => fullData ? deriveForYears(fullData, effectiveYears) : null,
    [fullData, effectiveYears],
  );

  const sectorPeerLinks = useMemo(() => {
    if (!allTickers?.length || !fullData) return [];
    const current = allTickers.find((ticker) => ticker.symbol === upperTicker);
    if (!current?.sector) return [];
    const peers = getSectorPeers(upperTicker, current.name, current.sector, allTickers, 8);
    return peers.map((symbol) => {
      const tickerData = allTickers.find((ticker) => ticker.symbol === symbol);
      return { symbol, name: tickerData?.name || "" };
    });
  }, [upperTicker, allTickers, fullData]);

  function switchTab(tab: TabKey) {
    router.push(buildTabPath(upperTicker, tab));
  }


  return (
    <div>

      {/* Company header */}
      {fullData && !isLoading && !error && (
        <div className="company-header">
          <div className="company-header-left">
            {fullData.logo && (
              <img
                className="company-header-logo"
                src={logoUrl(fullData.ticker)}
                alt={`Logo ${fullData.name}`}
                loading="lazy"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            )}
            <h2 className="company-header-name">{fullData.name} <span className="company-header-ticker">· {upperTicker}</span></h2>
          </div>
          <FavoriteButton ticker={upperTicker} />
        </div>
      )}

      {/* Tabs — pills on desktop, dropdown on mobile */}
      {!isLoading && !error && (
        <>
          <div className="tabs-wrapper tabs-desktop">
            <button
              className={`tab-pill ${activeTab === "metrics" ? "tab-pill-active" : ""}`}
              onClick={() => switchTab("metrics")}
            >
              {t("tabs.metrics")}
            </button>
            <button
              className={`tab-pill ${activeTab === "fundamentals" ? "tab-pill-active" : ""}`}
              onClick={() => switchTab("fundamentals")}
            >
              {t("tabs.fundamentals")}
            </button>
            <button
              className={`tab-pill ${activeTab === "compare" ? "tab-pill-active" : ""}`}
              onClick={() => switchTab("compare")}
            >
              {t("tabs.compare")}
            </button>
            <button
              className={`tab-pill ${activeTab === "charts" ? "tab-pill-active" : ""}`}
              onClick={() => switchTab("charts")}
            >
              {t("tabs.charts")}
            </button>
          </div>
          <div className="tabs-mobile">
            <select
              className="tabs-dropdown"
              value={activeTab}
              onChange={(e) => switchTab(e.target.value as "metrics" | "fundamentals" | "compare" | "charts")}
            >
              <option value="metrics">{t("tabs.metrics")}</option>
              <option value="fundamentals">{t("tabs.fundamentals")}</option>
              <option value="compare">{t("tabs.compare")}</option>
              <option value="charts">{t("tabs.charts")}</option>
            </select>
          </div>
        </>
      )}

      {/* Metrics tab */}
      {activeTab === "metrics" && (
        <>
          {isLoading && <CompanyMetricsCardLoading />}
          {derivedData && !isLoading && (
            <CompanyMetricsCard
              data={derivedData}
              years={effectiveYears}
              maxYears={maxYears}
              onYearsChange={setYears}
              sector={currentTicker?.sector}
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
            <MultiplesChart data={historyData} />
          )}
          {historyError && !historyLoading && (
            <div className="chart-container">
              <div className="chart-error">{(historyError as Error).message}</div>
            </div>
          )}
        </>
      )}

      {/* Fundamentals tab */}
      {activeTab === "fundamentals" && (
        <FundamentalsTab ticker={upperTicker} />
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
          savedListId={activeListId}
        />
      )}

      {/* AI Analysis */}
      {fullData && !isLoading && !error && (
        <CompanyAnalysis ticker={upperTicker} />
      )}

      {/* Sector peers */}
      {sectorPeerLinks.length > 0 && (
        <div className="pe10-card">
          <nav className="card-section" aria-label={t("sector.same_sector")}>
            <div className="card-section-heading">{t("sector.same_sector")}</div>
            <div className="sector-peers-list">
              {sectorPeerLinks.map((peer) => (
                <Link
                  key={peer.symbol}
                  href={`/${peer.symbol}`}
                  className="sector-peer-link"
                >
                  {peer.symbol}
                  {peer.name && <span className="sector-peer-name">{peer.name}</span>}
                </Link>
              ))}
            </div>
          </nav>
        </div>
      )}

      <ShareButtons
        ticker={upperTicker}
        companyName={fullData?.name}
      />
    </div>
  );
}
