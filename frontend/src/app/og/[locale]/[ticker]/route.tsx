import { ImageResponse } from "next/og";
import { isSupportedLocale } from "../../../../lib/i18n-config";
import {
  OG_CARD_HEIGHT,
  OG_CARD_WIDTH,
  buildOgCardModel,
  fetchOgCardData,
  tickerFromOgImageParam,
  type OgCardModel,
} from "../../../../lib/og-card";

export const runtime = "nodejs";

/**
 * Per-company Open Graph card.
 *
 * Rendering one image per company means each page advertises a distinct
 * image URL. Social networks key their image caches by URL, so a company
 * whose card fails to ingest can no longer take the whole domain's previews
 * down with it — which is exactly what happened when every page shared a
 * single static JPEG.
 */

/** Palette lifted from `src/styles/global.css` so the card matches the app. */
const COLOR_ACCENT = "#1e40af";
const COLOR_INK = "#333333";
const COLOR_MUTED = "#5570a0";
const COLOR_BORDER = "#d0daea";
const COLOR_SURFACE = "#ffffff";

/** Only Geist Regular ships with `next/og`, so hierarchy comes from size and colour. */
const CARD_PADDING = 64;

const ONE_HOUR_IN_SECONDS = 3600;
const ONE_DAY_IN_SECONDS = 86400;
const ONE_WEEK_IN_SECONDS = 604800;

function cardCacheControl(): string {
  return [
    "public",
    `max-age=${ONE_HOUR_IN_SECONDS}`,
    `s-maxage=${ONE_DAY_IN_SECONDS}`,
    `stale-while-revalidate=${ONE_WEEK_IN_SECONDS}`,
  ].join(", ");
}

function CompanyCard({ model }: { model: OgCardModel }) {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        backgroundColor: COLOR_SURFACE,
        padding: CARD_PADDING,
        fontFamily: "Geist",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 34, letterSpacing: 8, color: COLOR_ACCENT }}>SPONDA</div>
        <div style={{ fontSize: 24, color: COLOR_MUTED }}>sponda.capital</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ fontSize: 68, color: COLOR_INK, lineHeight: 1.1 }}>{model.companyName}</div>
        {model.subtitle ? (
          <div style={{ display: "flex", marginTop: 12, fontSize: 30, color: COLOR_MUTED }}>
            {model.subtitle}
          </div>
        ) : null}
      </div>

      <div style={{ display: "flex", gap: 20 }}>
        {model.indicators.map((indicator) => (
          <div
            key={indicator.label}
            style={{
              display: "flex",
              flexDirection: "column",
              flex: 1,
              border: `1px solid ${COLOR_BORDER}`,
              borderRadius: 16,
              padding: "20px 24px",
            }}
          >
            <div style={{ fontSize: 22, letterSpacing: 2, color: COLOR_MUTED }}>
              {indicator.label}
            </div>
            <div style={{ marginTop: 8, fontSize: 50, color: COLOR_ACCENT }}>
              {indicator.value}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", fontSize: 26, color: COLOR_MUTED }}>{model.tagline}</div>
    </div>
  );
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ locale: string; ticker: string }> },
) {
  const { locale, ticker: tickerParam } = await params;

  if (!isSupportedLocale(locale)) {
    return new Response("Unknown locale", { status: 404 });
  }

  const ticker = tickerFromOgImageParam(tickerParam);
  if (!ticker) {
    return new Response("Not an Open Graph card URL", { status: 404 });
  }

  // A ticker the API knows nothing about still gets a card: the symbol and
  // the branding are worth more in a shared link than a broken image.
  const { name, sector, quote } = await fetchOgCardData(ticker);
  const model = buildOgCardModel({ ticker, locale, name, sector, quote });

  return new ImageResponse(<CompanyCard model={model} />, {
    width: OG_CARD_WIDTH,
    height: OG_CARD_HEIGHT,
    headers: { "Cache-Control": cardCacheControl() },
  });
}
