import { NextResponse } from "next/server";
import { BASE_URL, computeSitemapIds } from "../../lib/sitemap-data";

export const revalidate = 86400;

export async function GET() {
  const sitemaps = await computeSitemapIds();

  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...sitemaps.map(
      ({ id }) =>
        `  <sitemap><loc>${BASE_URL}/sitemap/${id}.xml</loc></sitemap>`,
    ),
    "</sitemapindex>",
  ].join("\n");

  return new NextResponse(xml, {
    headers: {
      "Content-Type": "application/xml",
      "Cache-Control": "public, max-age=86400, s-maxage=86400",
    },
  });
}
