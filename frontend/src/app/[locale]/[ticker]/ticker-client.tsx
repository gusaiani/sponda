"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useParams, usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
const CompanyMetricsCard = dynamic(
  () => import("../../../components/CompanyMetricsCard").then((mod) => mod.CompanyMetricsCard),
  { ssr: false }
);
const MultiplesChart = dynamic(
  () => import("../../../components/MultiplesChart").then((mod) => mod.MultiplesChart),
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
  () => import("../../../components/CompareTab").then((mod) => mod.CompareTab),
  { ssr: false }
);
const FundamentalsTab = dynamic(
  () => import("../../../components/FundamentalsTab").then((mod) => mod.FundamentalsTab),
  { ssr: false }
);
const CompanyAnalysis = dynamic(
  () => import("../../../components/CompanyAnalysis").then((mod) => mod.CompanyAnalysis),
  { ssr: false }
);
import { FavoriteButton } from "../../../components/FavoriteButton";
import { VisitedButton } from "../../../components/VisitedButton";
import { RevisitBanner } from "../../../components/RevisitBanner";
import { ShareButtons } from "../../../components/ShareButtons";
import { CompanyGradeCard } from "../../../components/CompanyGradeCard";
import { useLearningMode } from "../../../learning";
import {
  usePE10,
  fetchQuote,
  resolveLookupLimitAction,
  type QuoteResult,
} from "../../../hooks/usePE10";
import { AuthModal } from "../../../components/AuthModal";
import { setEmailVerificationPromptVisible } from "../../../utils/emailVerificationPrompt";
import { useTickerDetail } from "../../../hooks/useTickerDetail";
import { usePeers } from "../../../hooks/usePeers";
import { useMultiplesHistory, fetchMultiplesHistory } from "../../../hooks/useMultiplesHistory";
import { deriveForYears } from "../../../hooks/deriveForYears";
import { fetchFundamentals, useFundamentals } from "../../../hooks/useFundamentals";
import { useSavedLists } from "../../../hooks/useSavedLists";
import { logoUrl, currencyCode } from "../../../utils/format";
import { useTranslation } from "../../../i18n";
import { YearsSlider } from "../../../components/YearsSlider";
import { InflationToggle, type InflationMode } from "../../../components/InflationToggle";
import { TabPills } from "../../../components/TabPills";
import { SpondsTab } from "../../../components/social/SpondsTab";

const STALE_TIME = 30 * 60 * 1000;

const DEFAULT_YEARS = 10;

import { resolveTab, buildTabPath, type TabKey } from "../../../utils/tabs";

interface TickerPageClientProps {
  initialData?: QuoteResult | null;
}

export function TickerPageClient({ initialData }: TickerPageClientProps) {
  const { t, locale } = useTranslation();
  const { enabled: learningModeEnabled } = useLearningMode();
  const { ticker: rawTicker } = useParams<{ ticker: string }>();
  const upperTicker = (rawTicker || "").toUpperCase();
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const [years, setYears] = useState(() => {
    if (typeof window === "undefined") return DEFAULT_YEARS;
    const param = new URLSearchParams(window.location.search).get("years");
    if (!param) return DEFAULT_YEARS;
    const parsed = parseInt(param, 10);
    return parsed >= 1 && parsed <= 20 ? parsed : DEFAULT_YEARS;
  });
  const initialWithTickers = (() => {
    if (typeof window === "undefined") return [] as string[];
    const withParam = new URLSearchParams(window.location.search).get("with");
    if (!withParam) return [] as string[];
    return withParam
      .split(",")
      .map((ticker) => ticker.trim().toUpperCase())
      .filter(Boolean);
  })();
  const [compareTickers, setCompareTickers] = useState<string[]>(initialWithTickers);
  const [activeListId, setActiveListId] = useState<number | null>(null);
  const seededForTicker = useRef<string | null>(
    initialWithTickers.length > 0 ? upperTicker : null,
  );

  const activeTab = resolveTab(pathname);
  const tabBarRef = useRef<HTMLDivElement>(null);
  const [sliderFixedTop, setSliderFixedTop] = useState<number | null>(null);
  const [inflationMode, setInflationMode] = useState<InflationMode>("nominal");

  const { data: fullData, isLoading, error } = usePE10(upperTicker, initialData ?? undefined);

  // Daily company-lookup cap hit. Anonymous -> push to sign up via the
  // auth modal; logged-in-but-unverified -> nudge email verification
  // (the auth modal would be wrong, they already have an account).
  const lookupLimit = resolveLookupLimitAction(error);
  const [limitModalDismissed, setLimitModalDismissed] = useState(false);
  const limitModalTicker = useRef<string | null>(null);
  if (limitModalTicker.current !== upperTicker) {
    limitModalTicker.current = upperTicker;
    if (limitModalDismissed) setLimitModalDismissed(false);
  }
  useEffect(() => {
    if (lookupLimit?.kind === "verify-prompt") {
      setEmailVerificationPromptVisible(true);
    }
  }, [lookupLimit?.kind]);

  const { data: currentTicker } = useTickerDetail(upperTicker);
  const { data: peers = [] } = usePeers(upperTicker);
  const { data: fundamentalsData } = useFundamentals(upperTicker, true);
  const { lists } = useSavedLists();

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

  // Seed compare list with same-sector peers and prefetch their data
  useEffect(() => {
    if (seededForTicker.current === upperTicker) return;
    if (!peers.length) return;
    if (!fullData) return;

    const peerSymbols = peers.map((peer) => peer.symbol);
    setCompareTickers(peerSymbols);
    seededForTicker.current = upperTicker;

    for (const peer of peerSymbols) {
      queryClient.prefetchQuery({
        queryKey: ["pe10", peer],
        queryFn: () => fetchQuote(peer),
        staleTime: 30 * 60 * 1000,
      });
    }
  }, [upperTicker, peers, fullData, queryClient]);

  // Lazy: only fetch when charts tab is active
  const {
    data: historyData,
    isLoading: historyLoading,
    error: historyError,
  } = useMultiplesHistory(upperTicker, true);

  const maxYears = fullData?.maxYearsAvailable ?? DEFAULT_YEARS;
  const effectiveYears = Math.min(years, maxYears);

  const derivedData = useMemo(
    () => fullData ? deriveForYears(fullData, effectiveYears) : null,
    [fullData, effectiveYears],
  );

  // Pin the floating slider to the tab-bar row. The tab bar's Y shifts
  // after first paint (company header mounts when fullData arrives, web
  // fonts swap, cards reflow), so a single mount-time measurement locks
  // in a too-high value. Re-measure after paint and on every reflow of
  // the content above. Document-relative (top + scrollY) so the value is
  // correct even if the page restored a scroll position.
  useEffect(() => {
    const tabBar = tabBarRef.current;
    if (!tabBar) return;

    const measure = () => {
      const rect = tabBar.getBoundingClientRect();
      setSliderFixedTop(rect.top + window.scrollY);
    };

    const raf = requestAnimationFrame(measure);
    window.addEventListener("resize", measure);

    let resizeObserver: ResizeObserver | undefined;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(measure);
      resizeObserver.observe(document.body);
    }
    document.fonts?.ready.then(measure).catch(() => {});

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", measure);
      resizeObserver?.disconnect();
    };
  }, [isLoading, error, fullData, activeTab]);

  function switchTab(tab: TabKey) {
    router.push(buildTabPath(locale, upperTicker, tab));
  }

  function prefetchTabData(tab: TabKey) {
    if (tab === "charts") {
      queryClient.prefetchQuery({
        queryKey: ["multiples-history", upperTicker],
        queryFn: () => fetchMultiplesHistory(upperTicker),
        staleTime: STALE_TIME,
      });
    }
    if (tab === "fundamentals") {
      queryClient.prefetchQuery({
        queryKey: ["fundamentals", upperTicker],
        queryFn: () => fetchFundamentals(upperTicker),
        staleTime: STALE_TIME,
      });
    }
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
            <h2 className="company-header-name">{fullData.name} <span className="company-header-ticker">· {upperTicker} · {t("header.currency")}: {
              fullData.reportedCurrency && fullData.listingCurrency &&
              fullData.reportedCurrency !== fullData.listingCurrency
                ? `${fullData.listingCurrency} (${t("header.reportsIn")} ${fullData.reportedCurrency})`
                : currencyCode(upperTicker, fullData.reportedCurrency)
            }{learningModeEnabled && fullData.ratings?.overall != null ? " · " : ""}</span><CompanyGradeCard ratings={fullData.ratings ?? null} /></h2>
          </div>
          <div className="company-header-actions">
            <VisitedButton ticker={upperTicker} />
            <FavoriteButton ticker={upperTicker} />
          </div>
        </div>
      )}

      {!isLoading && !error && <RevisitBanner ticker={upperTicker} />}

      {/* Tab bar: tabs left, years slider floats fixed on the right (desktop) */}
      {!isLoading && !error && (
        <>
          <div className="tab-bar" ref={tabBarRef}>
            <TabPills
              ticker={upperTicker}
              activeTab={activeTab}
              onPrefetch={prefetchTabData}
            />
          </div>
          <div className="tabs-mobile">
            <select
              className="tabs-dropdown"
              value={activeTab}
              onChange={(e) => switchTab(e.target.value as TabKey)}
            >
              <option value="metrics">{t("tabs.metrics")}</option>
              <option value="fundamentals">{t("tabs.fundamentals")}</option>
              <option value="compare">{t("tabs.compare")}</option>
              <option value="charts">{t("tabs.charts")}</option>
              <option value="sponds">{t("tabs.sponds")}</option>
            </select>
          </div>
          {(activeTab === "metrics" || activeTab === "compare" || activeTab === "fundamentals") && maxYears > 1 && (
            <div className="years-slider-inline years-slider-inline--mobile">
              <YearsSlider years={effectiveYears} maxYears={maxYears} onYearsChange={setYears} />
              {activeTab === "fundamentals" && (
                <InflationToggle
                  mode={inflationMode}
                  onModeChange={setInflationMode}
                  reportedCurrency={fundamentalsData?.reportedCurrency}
                />
              )}
            </div>
          )}
        </>
      )}

      {/* Fixed slider (desktop) */}
      {!isLoading && !error && (activeTab === "metrics" || activeTab === "compare" || activeTab === "fundamentals") && maxYears > 1 && sliderFixedTop !== null && (
        <div className="years-slider-fixed" style={{ top: sliderFixedTop }}>
          <YearsSlider years={effectiveYears} maxYears={maxYears} onYearsChange={setYears} />
          {activeTab === "fundamentals" && (
            <InflationToggle
              mode={inflationMode}
              onModeChange={setInflationMode}
              reportedCurrency={fundamentalsData?.reportedCurrency}
            />
          )}
        </div>
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
              fundamentals={fundamentalsData?.years}
              quarterlyRatios={fundamentalsData?.quarterlyRatios}
              priceHistory={historyData?.prices}
            />
          )}
          {error && !isLoading && (
            <div className="pe10-card">
              <div className="pe10-error">
                {lookupLimit
                  ? `${t("quota.limit_reached")} ${lookupLimit.limit ?? ""} ${
                      locale === "pt" ? "consultas diárias" : "daily queries"
                    }.`
                  : (error as Error).message}
              </div>
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
        <FundamentalsTab ticker={upperTicker} years={effectiveYears} valueMode={inflationMode} />
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

      {/* Sponds tab */}
      {activeTab === "sponds" && (
        <SpondsTab ticker={upperTicker} />
      )}

      {/* AI Analysis */}
      {fullData && !isLoading && !error && (
        <CompanyAnalysis ticker={upperTicker} />
      )}

      {/* Sector peers */}
      {peers.length > 0 && (
        <div className="pe10-card">
          <nav className="card-section" aria-label={t("sector.same_sector")}>
            <div className="card-section-heading">{t("sector.same_sector")}</div>
            <div className="sector-peers-list">
              {peers.slice(0, 8).map((peer) => (
                <Link
                  key={peer.symbol}
                  href={`/${locale}/${peer.symbol}`}
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

      {lookupLimit?.kind === "auth-modal" && !limitModalDismissed && (
        <AuthModal
          message={`${t("quota.limit_reached")} ${lookupLimit.limit ?? ""} ${
            locale === "pt" ? "consultas diárias" : "daily queries"
          }. ${t("quota.create_account")} ${t("quota.to_continue")}`}
          onClose={() => setLimitModalDismissed(true)}
          onSuccess={() => {
            setLimitModalDismissed(true);
            queryClient.invalidateQueries({ queryKey: ["auth-user"] });
            queryClient.invalidateQueries({ queryKey: ["quota"] });
            queryClient.invalidateQueries({ queryKey: ["pe10", upperTicker] });
          }}
        />
      )}
    </div>
  );
}
