import { readFile } from "node:fs/promises";
import path from "node:path";
import { withJpegComment } from "../../../../lib/jpeg-comment";
import { siteOgArtworkFromParam, type SiteOgArtwork } from "../../../../lib/og-card";
import { buildOgImageResponse } from "../../../../lib/og-response";

export const runtime = "nodejs";

/**
 * Site card: the Open Graph image for pages with no company to render.
 *
 * The artwork is the same JPEG that used to be linked straight from
 * `public/images/`. Serving it through a route instead gives it a fresh URL
 * (social networks key their image caches by URL), a `Content-Length`, and
 * none of the validators X's crawler was endlessly re-checking; see
 * `src/lib/og-response.ts` for the reasoning. The comment stamp makes the
 * bytes distinct from every copy already published, so a network that
 * fingerprints content cannot map the new URL back onto a stuck entry.
 */

const ARTWORK_DIRECTORY = path.join(process.cwd(), "public", "images");
const ARTWORK_FILES: Record<SiteOgArtwork, string> = {
  pt: "sponda-og-v2.jpg",
  en: "sponda-og-en-v2.jpg",
};
const JPEG_MIME_TYPE = "image/jpeg";

function commentFor(artwork: SiteOgArtwork): string {
  return `Sponda OG site card ${artwork} /og/site`;
}

async function loadArtwork(artwork: SiteOgArtwork): Promise<Uint8Array> {
  const file = await readFile(path.join(ARTWORK_DIRECTORY, ARTWORK_FILES[artwork]));
  return withJpegComment(new Uint8Array(file), commentFor(artwork));
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ card: string }> },
) {
  const { card } = await params;
  const artwork = siteOgArtworkFromParam(card);
  if (!artwork) {
    return new Response("Not a site Open Graph card URL", { status: 404 });
  }
  return buildOgImageResponse(await loadArtwork(artwork), JPEG_MIME_TYPE);
}
